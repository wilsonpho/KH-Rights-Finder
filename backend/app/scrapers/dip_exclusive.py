"""D/IPR Exclusive Rights of Mark scraper.

Static-ish listing page with links to PDFs per brand.
Cached locally since it changes infrequently.
"""

from __future__ import annotations

import io
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScraperResult, register_scraper

logger = logging.getLogger(__name__)

_MAX_OCR_PAGES = 3
_OCR_DPI = 300
_MIN_TEXT_LAYER_CHARS = 200


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str | None, list[str]]:
    """Extract text from a PDF, falling back to OCR for scanned documents.

    Returns (extracted_text, warnings).  Never raises on bad input.
    """
    warnings: list[str] = []

    if not pdf_bytes or len(pdf_bytes) < 100:
        return None, ["pdf_too_small"]

    # ── Fast path: text-layer extraction via pypdf ────────────────────
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        text = "\n\n".join(pages_text).strip()

        if len(text) >= _MIN_TEXT_LAYER_CHARS:
            return _clean_text(text), warnings
    except Exception as exc:
        warnings.append(f"pypdf_failed: {exc}")

    # ── OCR fallback via PyMuPDF + pytesseract ────────────────────────
    try:
        import fitz
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        warnings.append(f"ocr_deps_missing: {exc}")
        return None, warnings

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        warnings.append(f"pdf_open_failed: {exc}")
        return None, warnings

    total_pages = len(doc)
    ocr_pages = min(total_pages, _MAX_OCR_PAGES)
    if total_pages > _MAX_OCR_PAGES:
        warnings.append(f"ocr_truncated: processed {ocr_pages}/{total_pages} pages")

    warnings.append("ocr_used")

    page_texts: list[str] = []
    mat = fitz.Matrix(_OCR_DPI / 72, _OCR_DPI / 72)

    for i in range(ocr_pages):
        try:
            pix = doc[i].get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(img)
            page_texts.append(page_text)
        except Exception as exc:
            warnings.append(f"ocr_page_{i}_failed: {exc}")
            page_texts.append("")

    doc.close()

    if not any(t.strip() for t in page_texts):
        return None, warnings

    if len(page_texts) == 1:
        combined = page_texts[0]
    else:
        parts = []
        for idx, t in enumerate(page_texts, 1):
            parts.append(f"--- page {idx} ---\n\n{t}")
        combined = "\n\n".join(parts)

    return _clean_text(combined), warnings


def _clean_text(text: str) -> str:
    """Normalize whitespace without parsing fields."""
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

_MIN_EXTRACTION_CHARS = 50


def extract_exclusive_rights_fields(text: str) -> dict:
    """Extract structured fields from exclusive-rights certificate text.

    Pure function — regex + heuristic matching anchored on common legal
    phrasing.  Returns a dict of extracted fields plus ``parse_warnings``.
    Fields that cannot be confidently identified remain absent (never
    inferred).
    """
    fields: dict = {}
    warnings: list[str] = []

    if not text or len(text.strip()) < _MIN_EXTRACTION_CHARS:
        warnings.append("text_too_short_for_extraction")
        fields["parse_warnings"] = warnings
        return fields

    # ── Rights holder ─────────────────────────────────────────────────
    # Require proper-case first word to filter OCR garble.
    # Middle words must also be proper-case, short acronyms, or connectors.
    # Use [ \t]+ (not \s+) to avoid matching across newlines.
    company_re = re.compile(
        r"((?:[A-Z][a-z]+)"
        r"(?:[ \t]+(?:[A-Z][a-z]+|[A-Z]{2,5}|&|of|and|the|de)){0,6}[ \t]+"
        r"(?:Company|Corporation|Corp|Inc|Ltd|Co\.\s*,?\s*Ltd|PLC|LLC|GmbH|S\.A\.|Pty))\b\.?",
    )
    company_matches = company_re.findall(text)
    unique_companies = list(
        dict.fromkeys(m.strip() for m in company_matches if len(m.strip()) > 5)
    )
    normalised_company_names = set(n.lower() for n in unique_companies)

    if len(normalised_company_names) == 1:
        fields["rights_holder"] = unique_companies[0]
    elif len(normalised_company_names) > 1:
        fields["rights_holder"] = unique_companies[0]
        warnings.append(f"multiple_company_names_found: {unique_companies}")
    else:
        warnings.append("rights_holder_not_found")

    # ── Scope ─────────────────────────────────────────────────────────
    text_lower = text.lower()
    has_import = bool(re.search(r"\bimport(?:ation|ing|s)?\b", text_lower))
    has_distribution = bool(re.search(r"\bdistribut(?:ion|e|ing|or)\b", text_lower))

    if has_import and has_distribution:
        fields["scope"] = "both"
    elif has_import:
        fields["scope"] = "import"
    elif has_distribution:
        fields["scope"] = "distribution"

    # ── Reference number ──────────────────────────────────────────────
    ref_re = re.compile(r"(KH[/\-][A-Za-z0-9/\-]{4,})")
    ref_matches = ref_re.findall(text)
    unique_refs = list(dict.fromkeys(r.strip() for r in ref_matches))

    if len(unique_refs) == 1:
        fields["reference_number"] = unique_refs[0]
    elif len(unique_refs) > 1:
        fields["reference_number"] = unique_refs[0]
        warnings.append(f"multiple_reference_numbers: {unique_refs}")

    # ── Validity dates ────────────────────────────────────────────────
    date_re = re.compile(
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})"
    )
    date_matches = date_re.findall(text)
    unique_dates = list(dict.fromkeys(d.strip() for d in date_matches))

    from_re = re.compile(
        r"(?:valid\s+from|effective\s+(?:from|date))\s*:?\s*"
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
        re.IGNORECASE,
    )
    to_re = re.compile(
        r"(?:valid\s+(?:to|until|through)|expir(?:y|es|ation)\s*(?:date)?)\s*:?\s*"
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
        re.IGNORECASE,
    )
    from_match = from_re.search(text)
    to_match = to_re.search(text)

    if from_match:
        fields["valid_from_raw"] = from_match.group(1)
    if to_match:
        fields["valid_to_raw"] = to_match.group(1)

    if not from_match and not to_match and len(unique_dates) > 2:
        warnings.append(f"multiple_validity_dates_found: {unique_dates}")

    fields["parse_warnings"] = warnings
    return fields


EXCLUSIVE_URL = (
    "https://dip.cambodiaip.gov.kh/TemplateTwo.aspx"
    "?childMasterMenuId=280464&lang=en&menuid=280464&parentId=78"
)


@register_scraper("dip_exclusive")
class DIPExclusiveScraper(BaseScraper):
    async def search(self, mark_name: str) -> list[ScraperResult]:
        async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=True) as client:
            resp = await client.get(EXCLUSIVE_URL)
            resp.raise_for_status()
            raw_bytes = resp.content
            return self._parse_and_match(resp.text, mark_name, raw_bytes)

    def _parse_and_match(self, html: str, mark_name: str, raw_bytes: bytes) -> list[ScraperResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[ScraperResult] = []
        search_lower = mark_name.lower()

        # Find content area — look for links and text entries
        content = soup.find("div", {"id": lambda x: x and "content" in str(x).lower()})
        if not content:
            content = soup.find("div", class_=lambda c: c and "content" in str(c).lower())
        if not content:
            content = soup  # Search whole page

        # Search through all links and text blocks
        for link in content.find_all("a", href=True):
            link_text = link.get_text(strip=True)
            if search_lower in link_text.lower():
                href = link["href"]
                pdf_url = href if href.endswith(".pdf") else None
                if pdf_url and not pdf_url.startswith("http"):
                    pdf_url = f"https://dip.cambodiaip.gov.kh/{pdf_url.lstrip('/')}"

                results.append(ScraperResult(
                    title=f"Exclusive Rights: {link_text}",
                    detail={
                        "brand": link_text,
                        "pdf_url": pdf_url,
                        "href": href,
                        "page": "exclusive_rights",
                    },
                    confidence=90,
                    raw_content=raw_bytes,
                    content_type="text/html",
                    source_url=EXCLUSIVE_URL,
                ))

        # Also check plain text nodes for brand mentions
        for element in content.find_all(string=True):
            text = element.strip()
            if search_lower in text.lower() and len(text) < 500:
                # Avoid duplicates from links already found
                if not any(text in (r.detail or {}).get("brand", "") for r in results):
                    results.append(ScraperResult(
                        title=f"Exclusive Rights mention: {text[:100]}",
                        detail={
                            "brand": text[:200],
                            "page": "exclusive_rights",
                        },
                        confidence=70,
                        raw_content=raw_bytes,
                        content_type="text/html",
                        source_url=EXCLUSIVE_URL,
                    ))

        return results
