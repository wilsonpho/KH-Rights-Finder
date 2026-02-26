"""D/IPR Exclusive Rights of Mark scraper.

Static-ish listing page with links to PDFs per brand.
Cached locally since it changes infrequently.
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScraperResult, register_scraper

logger = logging.getLogger(__name__)

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
