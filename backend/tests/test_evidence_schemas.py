"""Unit tests for evidence_schemas.py — pure logic, no DB required.

SQL snippet – inspect latest evidence rows after running a scrape:

    SELECT id, source, evidence_kind, schema_version,
           detail->>'raw_text' IS NOT NULL AS has_raw,
           detail->'parse_warnings'        AS warnings,
           confidence, found_at
    FROM evidence
    ORDER BY found_at DESC
    LIMIT 20;
"""

from __future__ import annotations

from datetime import date

import pytest

from app.evidence_schemas import (
    ExclusiveRightsEvidenceV1,
    TrademarkEvidenceV1,
    parse_evidence,
    _try_parse_date,
)


# ── Valid trademark ──────────────────────────────────────────────────

def test_valid_trademark_passes():
    detail = {
        "mark": "ANGKOR",
        "owner": "Cambodia Brewery Ltd",
        "app. no.": "KH/M/2020/12345",
        "reg. no.": "KH/M/R/67890",
        "status": "registered",
        "filing date": "2020-03-15",
        "registration date": "2021-01-10",
        "class": "32 33",
        "goods/services": "Beer, wine",
    }
    structured, kind, version = parse_evidence("dip_trademark", detail)

    assert kind == "trademark"
    assert version == 1
    assert structured["mark_name"] == "ANGKOR"
    assert structured["owner_name"] == "Cambodia Brewery Ltd"
    assert structured["application_number"] == "KH/M/2020/12345"
    assert structured["registration_number"] == "KH/M/R/67890"
    assert structured["status"] == "registered"
    assert structured["filing_date"] == "2020-03-15"
    assert structured["filing_date_raw"] == "2020-03-15"
    assert structured["registration_date"] == "2021-01-10"
    assert structured["class_numbers"] == ["32", "33"]
    assert structured["goods_services"] == "Beer, wine"
    assert structured["raw_text"]
    assert "_validation_failed" not in structured


# ── Valid exclusive rights ───────────────────────────────────────────

def test_valid_exclusive_passes():
    detail = {
        "brand": "HONDA",
        "pdf_url": "https://example.com/honda.pdf",
        "href": "/doc/honda.pdf",
        "page": "exclusive_rights",
    }
    structured, kind, version = parse_evidence("dip_exclusive", detail)

    assert kind == "exclusive_rights"
    assert version == 1
    assert structured["brand"] == "HONDA"
    assert structured["pdf_url"] == "https://example.com/honda.pdf"
    assert structured["raw_text"]
    assert "_validation_failed" not in structured


# ── Missing optional fields allowed ──────────────────────────────────

def test_trademark_only_raw_text():
    """Only raw_text is required; all other fields default to None."""
    structured, kind, version = parse_evidence("dip_trademark", {"status": "pending"})

    assert kind == "trademark"
    assert version == 1
    assert structured["status"] == "pending"
    assert structured["mark_name"] is None
    assert structured["filing_date"] is None
    assert "_validation_failed" not in structured


def test_exclusive_only_raw_text():
    structured, kind, version = parse_evidence("dip_exclusive", {"page": "exclusive_rights"})

    assert kind == "exclusive_rights"
    assert version == 1
    assert structured["brand"] is None
    assert "_validation_failed" not in structured


# ── Empty detail dict → valid with raw_text='{}' ─────────────────────

def test_empty_detail_returns_valid_raw_text():
    structured, kind, version = parse_evidence("dip_trademark", {})

    assert kind == "trademark"
    assert version == 1
    assert structured["raw_text"] == "{}"
    assert structured["parse_warnings"] == []
    assert "_validation_failed" not in structured


def test_empty_detail_exclusive():
    structured, kind, version = parse_evidence("dip_exclusive", {})

    assert kind == "exclusive_rights"
    assert version == 1
    assert structured["raw_text"] == "{}"
    assert "_validation_failed" not in structured


# ── Date parsing ─────────────────────────────────────────────────────

def test_date_parse_iso():
    parsed, raw, warnings = _try_parse_date("2024-01-15")
    assert parsed == date(2024, 1, 15)
    assert raw == "2024-01-15"
    assert warnings == []


def test_date_parse_dd_mm_yyyy():
    parsed, raw, warnings = _try_parse_date("15/01/2024")
    assert parsed == date(2024, 1, 15)
    assert raw == "15/01/2024"
    assert warnings == []


def test_date_parse_invalid():
    parsed, raw, warnings = _try_parse_date("not-a-date")
    assert parsed is None
    assert raw == "not-a-date"
    assert len(warnings) == 1
    assert "Unparseable" in warnings[0]


def test_date_parse_none():
    parsed, raw, warnings = _try_parse_date(None)
    assert parsed is None
    assert raw is None
    assert warnings == []


def test_date_parse_empty_string():
    parsed, raw, warnings = _try_parse_date("")
    assert parsed is None
    assert raw is None
    assert warnings == []


def test_date_warning_flows_into_parse_evidence():
    detail = {"filing date": "garbage-date", "status": "pending"}
    structured, kind, _ = parse_evidence("dip_trademark", detail)

    assert structured["filing_date"] is None
    assert structured["filing_date_raw"] == "garbage-date"
    assert any("Unparseable" in w for w in structured["parse_warnings"])


# ── Validation error → fallback ──────────────────────────────────────

def test_validation_error_returns_fallback():
    """scope must be one of import/distribution/both/None — trigger error."""
    detail = {"scope": "INVALID_ENUM_VALUE"}
    structured, kind, version = parse_evidence("dip_exclusive", detail)

    assert kind == "exclusive_rights"
    assert version == 1
    assert structured.get("_validation_failed") is True
    assert structured["raw_text"]
    assert any("ValidationError" in w for w in structured["parse_warnings"])


def test_validation_fallback_confidence_contract():
    """Caller (_store_evidence) must set confidence=20 when _validation_failed."""
    detail = {"scope": "NOT_VALID"}
    structured, _, _ = parse_evidence("dip_exclusive", detail)
    assert structured.get("_validation_failed") is True

    confidence = 90
    if structured.pop("_validation_failed", False):
        confidence = 20
    assert confidence == 20


# ── Unknown source ───────────────────────────────────────────────────

def test_unknown_source_returns_raw():
    structured, kind, version = parse_evidence("some_other_scraper", {"foo": "bar"})

    assert kind == "unknown"
    assert version == 0
    assert structured["raw_text"]
    assert "_validation_failed" not in structured
