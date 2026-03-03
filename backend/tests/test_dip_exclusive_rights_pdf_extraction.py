"""Tests for exclusive-rights PDF extraction pipeline.

Fixtures:
  fixtures/dip_exclusive_rights/listing_example.html
      — Real DIP exclusive-rights listing page (fetched 2026-02-28).
        Contains 59 PDF links with brand names like Ford, Bentley, etc.

  fixtures/dip_exclusive_rights/certificate_example.pdf
      — Real exclusive-rights certificate for "Ford" (scanned image, 1 page).
        Downloaded from DIP, ~1.4 MB.  No text layer — requires OCR.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "dip_exclusive_rights"
LISTING_HTML = FIXTURES_DIR / "listing_example.html"
CERTIFICATE_PDF = FIXTURES_DIR / "certificate_example.pdf"

MIN_PDF_SIZE = 10_240  # 10 KB — a real certificate is ~1 MB


def _tesseract_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


requires_tesseract = pytest.mark.skipif(
    not _tesseract_available(),
    reason="tesseract binary not installed — install via `brew install tesseract` or `apt-get install tesseract-ocr`",
)

requires_pdf_fixture = pytest.mark.skipif(
    not CERTIFICATE_PDF.exists(),
    reason=f"PDF fixture missing: {CERTIFICATE_PDF}",
)


# ── Fixture sanity checks ────────────────────────────────────────────


class TestFixturesExist:
    def test_listing_fixture_exists(self):
        assert LISTING_HTML.exists(), f"Missing fixture: {LISTING_HTML}"
        size = LISTING_HTML.stat().st_size
        assert size > 1_000, f"Listing HTML too small ({size} bytes) — probably truncated"

    def test_pdf_fixture_exists_and_is_reasonable(self):
        if not CERTIFICATE_PDF.exists():
            pytest.skip(
                f"PDF fixture missing: {CERTIFICATE_PDF}  — "
                "download a real certificate from DIP and place it here"
            )
        size = CERTIFICATE_PDF.stat().st_size
        assert size > MIN_PDF_SIZE, (
            f"PDF fixture too small ({size} bytes, need >{MIN_PDF_SIZE}).  "
            "Replace with a real exclusive-rights certificate."
        )

    def test_listing_contains_pdf_links(self):
        html = LISTING_HTML.read_text(errors="replace")
        assert ".pdf" in html.lower(), "Listing HTML contains no PDF links"
        count = html.lower().count(".pdf")
        assert count >= 5, f"Expected ≥5 PDF links, found {count}"


# ── extract_pdf_text import + signature ──────────────────────────────


class TestExtractPdfTextBasics:
    def test_extract_pdf_text_importable(self):
        """extract_pdf_text must exist in dip_exclusive module."""
        try:
            from app.scrapers.dip_exclusive import extract_pdf_text
        except ImportError:
            pytest.fail(
                "extract_pdf_text not implemented yet — "
                "add it to backend/app/scrapers/dip_exclusive.py"
            )

    def test_extract_pdf_text_returns_tuple(self):
        from app.scrapers.dip_exclusive import extract_pdf_text

        result = extract_pdf_text(b"not-a-pdf")
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 2, f"Expected 2-tuple, got length {len(result)}"
        text, warnings = result
        assert text is None, "Should return None for garbage input"
        assert isinstance(warnings, list)

    def test_empty_bytes_returns_none(self):
        from app.scrapers.dip_exclusive import extract_pdf_text

        text, warnings = extract_pdf_text(b"")
        assert text is None
        assert any("too_small" in w for w in warnings)


# ── OCR extraction on real scanned PDF ───────────────────────────────


class TestOcrExtraction:
    @requires_tesseract
    @requires_pdf_fixture
    def test_extract_pdf_text_returns_nonempty_text_for_scanned_pdf(self):
        from app.scrapers.dip_exclusive import extract_pdf_text

        pdf_bytes = CERTIFICATE_PDF.read_bytes()
        text, warnings = extract_pdf_text(pdf_bytes)

        assert text is not None, f"OCR returned None.  Warnings: {warnings}"
        assert len(text) >= 200, (
            f"Extracted text too short ({len(text)} chars).  "
            f"Warnings: {warnings}\nFirst 300 chars: {text[:300]!r}"
        )
        assert "ocr_used" in warnings, (
            "Scanned PDF should trigger OCR fallback — expected 'ocr_used' in warnings"
        )

    @requires_tesseract
    @requires_pdf_fixture
    def test_ocr_text_contains_anchor_keywords(self):
        from app.scrapers.dip_exclusive import extract_pdf_text

        pdf_bytes = CERTIFICATE_PDF.read_bytes()
        text, _ = extract_pdf_text(pdf_bytes)
        assert text is not None

        anchor_keywords = [
            "ford", "Ford Motor Company",
            "exclusive", "rights",
            "import", "distribution", "commerce",
            "cambodia", "kingdom",
        ]
        text_lower = text.lower()
        found = [kw for kw in anchor_keywords if kw.lower() in text_lower]
        assert found, (
            f"OCR text contains none of: {anchor_keywords}\n"
            f"First 500 chars: {text[:500]!r}"
        )

    @requires_tesseract
    def test_clean_text_collapses_whitespace(self):
        from app.scrapers.dip_exclusive import _clean_text

        raw = "  hello   world  \n\n\n\n\nfoo  "
        cleaned = _clean_text(raw)
        assert "   " not in cleaned
        assert "\n\n\n" not in cleaned
        assert cleaned == "hello world\n\nfoo"


# ── extract_exclusive_rights_fields unit tests ───────────────────────


class TestExtractExclusiveRightsFields:
    def test_single_company_extracted(self):
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        text = "The rights are granted to Acme Trading Company for import."
        fields = extract_exclusive_rights_fields(text)

        assert fields["rights_holder"] == "Acme Trading Company"
        assert fields["scope"] == "import"

    def test_distribution_scope(self):
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        text = "Exclusive distribution rights held by Phnom Penh Corp in Cambodia."
        fields = extract_exclusive_rights_fields(text)

        assert fields.get("scope") == "distribution"

    def test_both_scope(self):
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        text = "Exclusive import and distribution by Global Motors Ltd for the Kingdom."
        fields = extract_exclusive_rights_fields(text)

        assert fields.get("scope") == "both"

    def test_no_company_found(self):
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        text = "This is a garbled OCR text with no recognizable company names at all." * 3
        fields = extract_exclusive_rights_fields(text)

        assert "rights_holder" not in fields
        assert "rights_holder_not_found" in fields["parse_warnings"]

    def test_short_text_warns(self):
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        fields = extract_exclusive_rights_fields("too short")
        assert "text_too_short_for_extraction" in fields["parse_warnings"]

    def test_contextual_date_extraction(self):
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        text = (
            "Grant of exclusive rights to Sample Trading Company "
            "valid from 01/06/2024 until expiry date 31/12/2025 "
            "for import and distribution of goods."
        )
        fields = extract_exclusive_rights_fields(text)

        assert fields.get("valid_from_raw") == "01/06/2024"
        assert fields.get("valid_to_raw") == "31/12/2025"

    def test_ambiguous_dates_produce_warning_not_inference(self):
        """Multiple dates without context → null fields + warning."""
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        text = (
            "Certificate for Best Motors Company regarding exclusive import.\n"
            "Date: 15/03/2023\n"
            "Signed: 20/04/2023\n"
            "Issued: 01/01/2024\n"
        )
        fields = extract_exclusive_rights_fields(text)

        assert fields.get("valid_from_raw") is None, (
            "Should NOT guess which date is valid_from without contextual cues"
        )
        assert fields.get("valid_to_raw") is None, (
            "Should NOT guess which date is valid_to without contextual cues"
        )
        assert any(
            "multiple_validity_dates_found" in w
            for w in fields["parse_warnings"]
        ), "Expected warning about multiple dates"

    def test_kh_reference_number(self):
        from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

        text = "Certificate No. KH/M/2023/00456 granted to Example Corp for distribution."
        fields = extract_exclusive_rights_fields(text)

        assert fields.get("reference_number") == "KH/M/2023/00456"


# ── End-to-end evidence mapping ──────────────────────────────────────


class TestExclusiveRightsEvidenceMapping:
    @requires_tesseract
    @requires_pdf_fixture
    def test_exclusive_rights_pdf_extracts_rights_holder(self):
        """End-to-end: PDF bytes → OCR → parse_evidence → structured fields.

        Asserts:
        - rights_holder is extracted from OCR text
        - parse_warnings includes 'ocr_used'
        - Fields that can't be extracted from Khmer-only OCR remain null
        """
        from app.scrapers.dip_exclusive import extract_pdf_text
        from app.evidence_schemas import parse_evidence

        pdf_bytes = CERTIFICATE_PDF.read_bytes()
        text, ocr_warnings = extract_pdf_text(pdf_bytes)

        assert text is not None, f"extract_pdf_text returned None: {ocr_warnings}"
        assert len(text.strip()) > 100

        detail = {
            "brand": "Ford",
            "pdf_url": "fixture://certificate_example.pdf",
            "_raw_text": text,
            "_pdf_warnings": ocr_warnings,
        }
        structured, kind, version = parse_evidence("dip_exclusive", detail)

        assert kind == "exclusive_rights"
        assert version == 1

        assert structured.get("rights_holder") is not None, (
            "rights_holder must be populated from the certificate.  "
            f"Got structured keys: {sorted(structured.keys())}"
        )
        assert "Ford Motor Company" in structured["rights_holder"]

        assert "ocr_used" in structured["parse_warnings"], (
            "parse_warnings should contain 'ocr_used' for scanned PDFs"
        )

        assert structured.get("brand") == "Ford"
        assert structured.get("pdf_url") == "fixture://certificate_example.pdf"

        # Khmer document without English dates/scope — these must remain null
        assert structured.get("scope") is None, (
            "scope should be null — Khmer text, no English import/distribution keywords"
        )
        assert structured.get("valid_from") is None
        assert structured.get("valid_to") is None

    def test_listing_fields_take_precedence_over_extraction(self):
        """Listing-provided values must not be overwritten by extraction."""
        from app.evidence_schemas import parse_evidence

        text = "Exclusive import by Override Motors Company for Cambodia."
        detail = {
            "brand": "OriginalBrand",
            "rights_holder": "ListingHolder",
            "pdf_url": "https://example.com/cert.pdf",
            "_raw_text": text,
        }
        structured, kind, _ = parse_evidence("dip_exclusive", detail)

        assert kind == "exclusive_rights"
        assert structured["brand"] == "OriginalBrand"
        assert structured["rights_holder"] == "ListingHolder", (
            "Listing-provided rights_holder must take precedence over extraction"
        )

    def test_parse_evidence_with_pdf_warnings(self):
        """OCR warnings passed via _pdf_warnings flow into parse_warnings."""
        from app.evidence_schemas import parse_evidence

        text = "Certificate for Sample Motors Company regarding exclusive distribution." * 5
        detail = {
            "brand": "Sample",
            "_raw_text": text,
            "_pdf_warnings": ["ocr_used", "ocr_truncated: processed 3/5 pages"],
        }
        structured, kind, _ = parse_evidence("dip_exclusive", detail)

        assert kind == "exclusive_rights"
        assert "ocr_used" in structured["parse_warnings"]
        assert any("ocr_truncated" in w for w in structured["parse_warnings"])
