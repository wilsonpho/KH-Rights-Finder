"""Tests for DIP trademark HTML parsing and evidence field population.

Covers:
  - _extract_table_rows against realistic DIP GridView HTML
  - End-to-end: scraper detail → parse_evidence → TrademarkEvidenceV1 fields
  - Missing field → null (no inference)
  - _normalise_label edge cases
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.evidence_schemas import parse_evidence
from app.scrapers.dip_trademark import DIPTrademarkScraper, _normalise_label, _parse_record_cell


# ---------------------------------------------------------------------------
# Fixtures — minimal HTML that mirrors real DIP GridView structure
# ---------------------------------------------------------------------------

SINGLE_RECORD_HTML = """\
<table class="grid-list mark-list" id="ctl00_PanelSingle_MarkSearchControl_gvList">
  <tr>
    <td align="center" width="5%">
      <table style="width: 100%;">
        <tr>
          <td style="width: 200px">
            <h5>ANGKOR BEER</h5>
          </td>
          <td>
            <table style="width: 100%;" class="info-list-detail">
              <tr>
                <td style="width: 150px;"><p>Application number:</p></td>
                <td>KH/T/2020/12345</td>
              </tr>
              <tr>
                <td><p>Application date:</p></td>
                <td>2020-03-15</td>
              </tr>
              <tr>
                <td><p>Owner Name: </p></td>
                <td>Cambodia Brewery Ltd</td>
              </tr>
              <tr>
                <td><p>Owner Address: </p></td>
                <td>Phnom Penh, Cambodia</td>
              </tr>
              <tr>
                <td><p>Nice classification:</p></td>
                <td>32 33</td>
              </tr>
            </table>
          </td>
          <td>
            <a href="#dialog" class="link-dialog">
              <img src="Marks/2020/12345.jpg" alt="KH/T/2020/12345"
                   class="mark-logo" onerror="this.style.display='none'" />
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
"""

TWO_RECORDS_HTML = """\
<table class="grid-list mark-list" id="gvList">
  <tr>
    <td>
      <table>
        <tr>
          <td><h5>COCA-COLA</h5></td>
          <td>
            <table class="info-list-detail">
              <tr><td><p>Application number:</p></td><td>KH/T/1995/001</td></tr>
              <tr><td><p>Application date:</p></td><td>1995-06-01</td></tr>
              <tr><td><p>Owner Name:</p></td><td>The Coca-Cola Company</td></tr>
              <tr><td><p>Owner Address:</p></td><td>Atlanta, USA</td></tr>
              <tr><td><p>Nice classification:</p></td><td>32</td></tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td>
      <table>
        <tr>
          <td><h5>FANTA</h5></td>
          <td>
            <table class="info-list-detail">
              <tr><td><p>Application number:</p></td><td>KH/T/1996/002</td></tr>
              <tr><td><p>Application date:</p></td><td>1996-12-20</td></tr>
              <tr><td><p>Owner Name:</p></td><td>The Coca-Cola Company</td></tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
"""

MISSING_FIELDS_HTML = """\
<table class="grid-list mark-list" id="gvList">
  <tr>
    <td>
      <table>
        <tr>
          <td><h5>MYSTERY BRAND</h5></td>
          <td>
            <table class="info-list-detail">
              <tr><td><p>Application number:</p></td><td>KH/T/2024/99999</td></tr>
              <tr><td><p>Nice classification:</p></td><td></td></tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
"""


# ---------------------------------------------------------------------------
# _normalise_label
# ---------------------------------------------------------------------------

class TestNormaliseLabel:

    def test_strips_trailing_colon(self):
        assert _normalise_label("Application number:") == "application number"

    def test_strips_colon_with_space(self):
        assert _normalise_label("Owner Name: ") == "owner name"

    def test_preserves_inner_spaces(self):
        assert _normalise_label("Nice classification:") == "nice classification"

    def test_collapses_whitespace(self):
        assert _normalise_label("  Owner   Address :  ") == "owner address"

    def test_plain_label(self):
        assert _normalise_label("status") == "status"


# ---------------------------------------------------------------------------
# _parse_record_cell
# ---------------------------------------------------------------------------

class TestParseRecordCell:

    def test_extracts_mark_name(self):
        soup = BeautifulSoup(SINGLE_RECORD_HTML, "html.parser")
        tr = soup.find("table", class_="grid-list").find("tr", recursive=False)
        detail = _parse_record_cell(tr)
        assert detail is not None
        assert detail["mark name"] == "ANGKOR BEER"

    def test_extracts_all_fields(self):
        soup = BeautifulSoup(SINGLE_RECORD_HTML, "html.parser")
        tr = soup.find("table", class_="grid-list").find("tr", recursive=False)
        detail = _parse_record_cell(tr)

        assert detail["application number"] == "KH/T/2020/12345"
        assert detail["application date"] == "2020-03-15"
        assert detail["owner name"] == "Cambodia Brewery Ltd"
        assert detail["owner address"] == "Phnom Penh, Cambodia"
        assert detail["nice classification"] == "32 33"

    def test_returns_none_for_empty_row(self):
        soup = BeautifulSoup("<tr><td></td></tr>", "html.parser")
        tr = soup.find("tr")
        assert _parse_record_cell(tr) is None


# ---------------------------------------------------------------------------
# _extract_table_rows
# ---------------------------------------------------------------------------

class TestExtractTableRows:

    def test_single_record(self):
        soup = BeautifulSoup(SINGLE_RECORD_HTML, "html.parser")
        table = soup.find("table", class_="grid-list")
        results = DIPTrademarkScraper._extract_table_rows(table, b"<html>...</html>")

        assert len(results) == 1
        r = results[0]
        assert r.title == "ANGKOR BEER"
        assert r.detail["mark name"] == "ANGKOR BEER"
        assert r.detail["application number"] == "KH/T/2020/12345"
        assert r.detail["owner name"] == "Cambodia Brewery Ltd"
        assert r.confidence == 50

    def test_two_records(self):
        soup = BeautifulSoup(TWO_RECORDS_HTML, "html.parser")
        table = soup.find("table", class_="grid-list")
        results = DIPTrademarkScraper._extract_table_rows(table, b"...")

        assert len(results) == 2
        assert results[0].title == "COCA-COLA"
        assert results[1].title == "FANTA"
        assert results[1].detail["application number"] == "KH/T/1996/002"

    def test_raw_text_is_clean(self):
        soup = BeautifulSoup(SINGLE_RECORD_HTML, "html.parser")
        table = soup.find("table", class_="grid-list")
        results = DIPTrademarkScraper._extract_table_rows(table, b"...")
        raw = results[0].detail["_raw_text"]

        assert raw.startswith("ANGKOR BEER")
        assert "application number: KH/T/2020/12345" in raw
        assert "owner name: Cambodia Brewery Ltd" in raw


# ---------------------------------------------------------------------------
# End-to-end: scraper detail → parse_evidence → structured fields
# ---------------------------------------------------------------------------

class TestParseEvidenceIntegration:

    def _scrape_single(self):
        """Helper: parse the single-record fixture and return the detail dict."""
        soup = BeautifulSoup(SINGLE_RECORD_HTML, "html.parser")
        table = soup.find("table", class_="grid-list")
        results = DIPTrademarkScraper._extract_table_rows(table, b"...")
        return results[0].detail

    def test_structured_fields_populated(self):
        detail = self._scrape_single()
        structured, kind, version = parse_evidence("dip_trademark", detail)

        assert kind == "trademark"
        assert version == 1
        assert structured["mark_name"] == "ANGKOR BEER"
        assert structured["owner_name"] == "Cambodia Brewery Ltd"
        assert structured["owner_address"] == "Phnom Penh, Cambodia"
        assert structured["application_number"] == "KH/T/2020/12345"
        assert structured["filing_date"] == "2020-03-15"
        assert structured["filing_date_raw"] == "2020-03-15"
        assert structured["class_numbers"] == ["32", "33"]
        assert structured["raw_text"]
        assert "_validation_failed" not in structured
        assert "_raw_text" not in structured

    def test_raw_text_not_json_garbage(self):
        detail = self._scrape_single()
        structured, _, _ = parse_evidence("dip_trademark", detail)
        raw = structured["raw_text"]

        assert "ANGKOR BEER" in raw
        assert "KH/T/2020/12345" in raw
        assert "__VIEWSTATE" not in raw
        assert "_raw_text" not in raw

    def test_raw_text_not_in_json_text_either(self):
        """_raw_text must be popped before json_text is computed."""
        detail = self._scrape_single()
        structured, _, _ = parse_evidence("dip_trademark", detail)
        raw = structured["raw_text"]
        assert "_raw_text" not in raw

    def test_missing_fields_stay_null(self):
        """Fields absent from HTML must remain null — never inferred."""
        soup = BeautifulSoup(MISSING_FIELDS_HTML, "html.parser")
        table = soup.find("table", class_="grid-list")
        results = DIPTrademarkScraper._extract_table_rows(table, b"...")
        detail = results[0].detail

        structured, kind, _ = parse_evidence("dip_trademark", detail)

        assert kind == "trademark"
        assert structured["mark_name"] == "MYSTERY BRAND"
        assert structured["application_number"] == "KH/T/2024/99999"
        assert structured["owner_name"] is None
        assert structured["owner_address"] is None
        assert structured["filing_date"] is None
        assert structured["registration_number"] is None
        assert structured["class_numbers"] is None
        assert structured["goods_services"] is None

    def test_application_date_maps_to_filing_date(self):
        """DIP says 'Application date' — FIELD_MAP must route it to filing_date_raw."""
        detail = self._scrape_single()
        structured, _, _ = parse_evidence("dip_trademark", detail)

        assert structured["filing_date_raw"] == "2020-03-15"
        assert structured["filing_date"] == "2020-03-15"

    def test_empty_status_becomes_null(self):
        """DIP records without a status field should yield status=None, not ''."""
        detail = self._scrape_single()
        structured, _, _ = parse_evidence("dip_trademark", detail)
        assert structured["status"] is None

    def test_raw_text_lives_inside_detail_dict(self):
        """raw_text must be a key inside the structured dict (stored as detail JSONB).

        There is no evidence.raw_text column — the DB stores it at
        evidence.detail->>'raw_text'.  This test guards against regressions
        where raw_text is accidentally omitted from the detail dict.
        """
        detail = self._scrape_single()
        structured, _, _ = parse_evidence("dip_trademark", detail)

        assert "raw_text" in structured
        assert isinstance(structured["raw_text"], str)
        assert len(structured["raw_text"]) > 0
        assert "ANGKOR BEER" in structured["raw_text"]
