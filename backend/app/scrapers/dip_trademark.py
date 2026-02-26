"""D/IPR Trademark Search scraper (SearchMark.aspx).

ASP.NET WebForms — requires extracting the full form state from the
page, then POSTing with every hidden field plus the search term and
the submit button name/value.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import settings
from app.scrapers.base import BaseScraper, ScraperResult, register_scraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://dip.cambodiaip.gov.kh/SearchMark.aspx?lang=en"

SNAPSHOT_DIR = Path("/data/snapshots")

ERROR_MARKERS = re.compile(
    r"no records? found|access denied|captcha|forbidden|blocked|"
    r"unusual traffic|rate limit|service unavailable|error occurred",
    re.IGNORECASE,
)

_MARK_TEXTBOX_RE = re.compile(r"txtMark|MarkName|Mark.*Search|Search.*Mark", re.IGNORECASE)

NO_RECORDS_RE = re.compile(
    r"no\s+records?\s+found|no\s+results?\s+found|no\s+data\s+found|"
    r"no\s+matching\s+records?|0\s+records?\s+found",
    re.IGNORECASE,
)


@register_scraper("dip_trademark")
class DIPTrademarkScraper(BaseScraper):

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def search(self, mark_name: str) -> list[ScraperResult]:
        debug = settings.scraper_debug
        async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=True) as client:
            # Step 1: GET the search page
            resp = await client.get(SEARCH_URL)
            resp.raise_for_status()

            if debug:
                self._log_response("GET", resp, mark_name)

            soup = BeautifulSoup(resp.text, "html.parser")
            form = soup.find("form", id="aspnetForm") or soup.find("form")
            if not form:
                raise RuntimeError("No <form> found on SearchMark page")

            # Step 2: collect ALL hidden inputs as-is
            payload: dict[str, str] = {}
            for inp in form.find_all("input", {"type": "hidden"}):
                name = inp.get("name")
                if name:
                    payload[name] = inp.get("value", "")

            # Ensure __EVENTTARGET / __EVENTARGUMENT present (ASP.NET postback)
            payload.setdefault("__EVENTTARGET", "")
            payload.setdefault("__EVENTARGUMENT", "")

            # Step 3: auto-discover mark textbox and set value
            textbox_name = self._find_textbox(form)
            payload[textbox_name] = mark_name

            # Step 4: auto-discover search submit button
            btn_name, btn_value = self._find_submit_button(form)
            payload[btn_name] = btn_value

            if debug:
                hidden_keys = sorted(
                    k for k in payload if k not in (textbox_name, btn_name)
                )
                logger.info(
                    "POST payload | textbox=%s | button=%s=%r | "
                    "hidden_count=%d (%s) | total_fields=%d",
                    textbox_name,
                    btn_name,
                    btn_value,
                    len(hidden_keys),
                    hidden_keys,
                    len(payload),
                )

            # Step 5: POST
            resp = await client.post(SEARCH_URL, data=payload)
            resp.raise_for_status()

            if debug:
                self._log_response("POST", resp, mark_name)

            raw_bytes = resp.content
            return self._parse_results(resp.text, raw_bytes, resp.status_code, mark_name)

    # ------------------------------------------------------------------
    # Form field auto-discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _find_textbox(form: Tag) -> str:
        """Auto-discover the mark-name textbox inside the form."""
        text_inputs = form.find_all("input", {"type": "text"})

        # Prefer input whose name/id matches a mark-related pattern
        for inp in text_inputs:
            name = inp.get("name", "")
            inp_id = inp.get("id", "")
            if _MARK_TEXTBOX_RE.search(name) or _MARK_TEXTBOX_RE.search(inp_id):
                return name

        # Fallback: first text input inside the MarkSearch panel
        for inp in text_inputs:
            name = inp.get("name", "")
            if "PanelSingle" in name or "MarkSearch" in name:
                return name

        # Last resort: first text input that isn't the site-wide search bar
        for inp in text_inputs:
            name = inp.get("name", "")
            if name and "SearchEngin" not in name:
                return name

        raise RuntimeError(
            f"Cannot find mark textbox; text inputs: "
            f"{[i.get('name') for i in text_inputs]}"
        )

    @staticmethod
    def _find_submit_button(form: Tag) -> tuple[str, str]:
        """Auto-discover the Search submit button. Returns (name, value)."""
        submits = form.find_all("input", {"type": "submit"})

        # Best match: value contains "Search" AND inside the MarkSearch panel
        for btn in submits:
            val = btn.get("value", "")
            name = btn.get("name", "")
            if "search" in val.lower() and "MarkSearch" in name:
                return name, val

        # Next: any submit in PanelSingle whose value or name hints "search"
        for btn in submits:
            val = btn.get("value", "")
            name = btn.get("name", "")
            if ("search" in val.lower() or "search" in name.lower()) and "PanelSingle" in name:
                return name, val

        # Fallback: first submit that isn't the site-wide search button
        for btn in submits:
            name = btn.get("name", "")
            if name and "SearchEngin" not in name:
                return name, btn.get("value", "")

        raise RuntimeError(
            f"Cannot find submit button; buttons: "
            f"{[(b.get('name'), b.get('value')) for b in submits]}"
        )

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _parse_results(
        self, html: str, raw_bytes: bytes, status_code: int, mark_name: str
    ) -> list[ScraperResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[ScraperResult] = []
        debug = settings.scraper_debug

        # Look for a results GridView table
        table = soup.find("table", {"id": lambda x: x and "GridView" in str(x)})
        if not table:
            table = soup.find("table", class_=lambda c: c and "grid" in str(c).lower())

        if table:
            if debug:
                logger.info("Results table found: id=%s", table.get("id"))
            results = self._extract_table_rows(table, raw_bytes)
            return results

        # No table — check if the page says "no records found" (genuine 0 results)
        page_text = soup.get_text(" ", strip=True)
        no_records_match = NO_RECORDS_RE.search(page_text)

        if no_records_match:
            if debug:
                logger.info(
                    "No-records marker found: %r", no_records_match.group()
                )
            return results

        # Neither results table nor "no records" message — wrong page / parse failure
        logger.warning(
            "dip_trademark: POST returned page without results table or "
            "no-records message (possible form submission failure)"
        )
        if debug:
            self._dump_debug(html, raw_bytes, status_code, mark_name, soup)

        raise RuntimeError(
            "DIP trademark search did not return a results page "
            "(no GridView and no 'no records' message)"
        )

    @staticmethod
    def _extract_table_rows(table: Tag, raw_bytes: bytes) -> list[ScraperResult]:
        rows = table.find_all("tr")
        if len(rows) < 2:
            return []

        headers = [
            th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])
        ]
        results: list[ScraperResult] = []

        for row in rows[1:]:
            cols = row.find_all("td")
            if not cols:
                continue

            detail: dict = {}
            for i, col in enumerate(cols):
                text = col.get_text(strip=True)
                if i < len(headers):
                    detail[headers[i]] = text
                else:
                    detail[f"col_{i}"] = text

            title = detail.get("mark", detail.get("mark name", detail.get("col_0", "")))
            status = detail.get("status", detail.get("col_4", "")).lower()
            detail["status"] = status

            results.append(ScraperResult(
                title=title or _mark_name_fallback(detail),
                detail=detail,
                confidence=80 if "registered" in status else 50,
                raw_content=raw_bytes,
                content_type="text/html",
                source_url=SEARCH_URL,
            ))

        return results

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log_response(method: str, resp: httpx.Response, mark_name: str) -> None:
        """Log response diagnostics (SCRAPER_DEBUG only)."""
        html = resp.text
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        page_title = title_match.group(1).strip()[:200] if title_match else "(no <title>)"

        searchmark_idx = html.find("SearchMark")
        has_viewstate = "__VIEWSTATE" in html

        form_ids = [
            tag.get("id") or tag.get("name") or "(anonymous)"
            for tag in BeautifulSoup(html, "html.parser").find_all("form")
        ]

        logger.info(
            "%s response | mark=%s | final_url=%s | HTTP %d | "
            "title=%.200s | has___VIEWSTATE=%s | "
            "SearchMark_at=%s | form_ids=%s",
            method,
            mark_name,
            resp.url,
            resp.status_code,
            page_title,
            has_viewstate,
            searchmark_idx if searchmark_idx >= 0 else "NOT FOUND",
            form_ids or "none",
        )

    def _dump_debug(
        self,
        html: str,
        raw_bytes: bytes,
        status_code: int,
        mark_name: str,
        soup: BeautifulSoup,
    ) -> None:
        """Persist failing HTML and log diagnostics (SCRAPER_DEBUG only)."""
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else "(no <title>)"

        visible_text = soup.get_text(" ", strip=True)
        error_hits = ERROR_MARKERS.findall(visible_text)

        logger.warning(
            "dip_trademark debug | mark=%s | HTTP %d | title=%s | "
            "error_markers=%s | html_preview=%.2000s",
            mark_name,
            status_code,
            page_title,
            error_hits or "none",
            html[:2000],
        )

        try:
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safe_name = re.sub(r"[^\w\-]", "_", mark_name)[:60]
            path = SNAPSHOT_DIR / f"dip_trademark_{safe_name}_{ts}.html"
            path.write_bytes(raw_bytes)
            logger.info("Saved debug snapshot → %s (%d bytes)", path, len(raw_bytes))
        except OSError:
            logger.exception("Failed to write debug snapshot")


def _mark_name_fallback(detail: dict) -> str:
    """Try to find a usable name from the detail dict."""
    for key in ("mark name", "mark", "name", "col_0", "col_1"):
        if key in detail and detail[key]:
            return detail[key]
    return "Unknown mark"
