"""Pydantic evidence schemas and parse_evidence() dispatcher.

Every evidence row stored via _store_evidence() passes through
parse_evidence(), which normalises scraper-produced keys, attempts
date parsing, and validates against the appropriate versioned schema.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Dict, List, Literal, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y")


def _try_parse_date(
    raw: Optional[str],
) -> Tuple[Optional[date], Optional[str], List[str]]:
    """Attempt to parse *raw* into a date using common formats.

    Returns (parsed_date, raw_string, warnings).
    """
    if not raw or not raw.strip():
        return None, None, []
    raw_stripped = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            parsed = (
                date.fromisoformat(raw_stripped)
                if fmt == "%Y-%m-%d"
                else _strptime(raw_stripped, fmt)
            )
            return parsed, raw_stripped, []
        except (ValueError, TypeError):
            continue
    return None, raw_stripped, [f"Unparseable date: {raw_stripped!r}"]


def _strptime(value: str, fmt: str) -> date:
    from datetime import datetime as _dt
    return _dt.strptime(value, fmt).date()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TrademarkEvidenceV1(BaseModel):
    raw_text: str
    parse_warnings: List[str] = []

    mark_name: Optional[str] = None
    owner_name: Optional[str] = None
    owner_address: Optional[str] = None
    application_number: Optional[str] = None
    registration_number: Optional[str] = None
    status: Optional[str] = None

    filing_date: Optional[date] = None
    filing_date_raw: Optional[str] = None
    registration_date: Optional[date] = None
    registration_date_raw: Optional[str] = None
    expiry_date: Optional[date] = None
    expiry_date_raw: Optional[str] = None

    class_numbers: Optional[List[str]] = None
    class_numbers_raw: Optional[str] = None
    goods_services: Optional[str] = None


class ExclusiveRightsEvidenceV1(BaseModel):
    raw_text: str
    parse_warnings: List[str] = []

    brand: Optional[str] = None
    rights_holder: Optional[str] = None
    principal: Optional[str] = None
    scope: Optional[Literal["import", "distribution", "both"]] = None

    reference_number: Optional[str] = None

    valid_from: Optional[date] = None
    valid_from_raw: Optional[str] = None
    valid_to: Optional[date] = None
    valid_to_raw: Optional[str] = None

    pdf_url: Optional[str] = None
    href: Optional[str] = None
    page: Optional[str] = None


# ---------------------------------------------------------------------------
# Per-source field maps  (scraper key -> schema key)
# ---------------------------------------------------------------------------

_TRADEMARK_FIELD_MAP: Dict[str, str] = {
    # Mark name
    "mark": "mark_name",
    "mark name": "mark_name",
    # Owner
    "owner": "owner_name",
    "owner name": "owner_name",
    "owner_name": "owner_name",
    # Owner address
    "address": "owner_address",
    "owner address": "owner_address",
    "owner_address": "owner_address",
    # Application number
    "app. no.": "application_number",
    "app no": "application_number",
    "application number": "application_number",
    "application_number": "application_number",
    # Registration number
    "reg. no.": "registration_number",
    "reg no": "registration_number",
    "registration number": "registration_number",
    "registration_number": "registration_number",
    # Status
    "status": "status",
    # Dates — DIP uses "application date" rather than "filing date"
    "filing date": "filing_date_raw",
    "filing_date": "filing_date_raw",
    "application date": "filing_date_raw",
    "registration date": "registration_date_raw",
    "registration_date": "registration_date_raw",
    "expiry date": "expiry_date_raw",
    "expiry_date": "expiry_date_raw",
    # Classification
    "class": "class_numbers_raw",
    "class_numbers": "class_numbers_raw",
    "nice classification": "class_numbers_raw",
    "international class": "class_numbers_raw",
    # Goods/services
    "goods/services": "goods_services",
    "goods_services": "goods_services",
    "goods services": "goods_services",
    "goods & services": "goods_services",
    "goods and services": "goods_services",
}

_EXCLUSIVE_FIELD_MAP: Dict[str, str] = {
    "brand": "brand",
    "rights_holder": "rights_holder",
    "rights holder": "rights_holder",
    "principal": "principal",
    "scope": "scope",
    "reference_number": "reference_number",
    "ref": "reference_number",
    "certificate": "reference_number",
    "decision": "reference_number",
    "valid_from": "valid_from_raw",
    "valid from": "valid_from_raw",
    "valid_to": "valid_to_raw",
    "valid to": "valid_to_raw",
    "pdf_url": "pdf_url",
    "href": "href",
    "page": "page",
}

_SOURCE_CONFIG: Dict[str, Tuple[Dict[str, str], Type[BaseModel], str]] = {
    "dip_trademark": (_TRADEMARK_FIELD_MAP, TrademarkEvidenceV1, "trademark"),
    "dip_exclusive": (_EXCLUSIVE_FIELD_MAP, ExclusiveRightsEvidenceV1, "exclusive_rights"),
}

_TRADEMARK_DATE_FIELDS = ("filing_date", "registration_date", "expiry_date")
_EXCLUSIVE_DATE_FIELDS = ("valid_from", "valid_to")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_evidence(
    source: str, detail: dict
) -> Tuple[dict, str, int]:
    """Normalise, validate, and structure a scraper detail dict.

    Returns (structured_detail, evidence_kind, schema_version).

    *structured_detail* always contains ``raw_text`` and
    ``parse_warnings``.  If validation fails the dict is a minimal
    fallback with ``_validation_failed = True`` so the caller can
    lower confidence.
    """
    raw_text = detail.pop("_raw_text", None)
    pdf_warnings: List[str] = detail.pop("_pdf_warnings", [])
    json_text = json.dumps(detail, sort_keys=True, default=str)
    raw_text = raw_text or json_text

    cfg = _SOURCE_CONFIG.get(source)
    if cfg is None:
        return {"raw_text": raw_text, "parse_warnings": []}, "unknown", 0

    field_map, model_cls, evidence_kind = cfg
    schema_version = 1

    normalised = _normalise_keys(detail, field_map)
    normalised["raw_text"] = raw_text

    warnings: List[str] = list(normalised.get("parse_warnings", []))
    warnings.extend(pdf_warnings)

    # For exclusive rights: extract structured fields from PDF/OCR text
    if evidence_kind == "exclusive_rights" and raw_text and len(raw_text) > 200:
        _enrich_from_pdf_text(normalised, raw_text, warnings)

    date_fields = (
        _TRADEMARK_DATE_FIELDS if evidence_kind == "trademark" else _EXCLUSIVE_DATE_FIELDS
    )
    for prefix in date_fields:
        raw_key = f"{prefix}_raw"
        raw_val = normalised.get(raw_key)
        parsed, kept_raw, date_warnings = _try_parse_date(raw_val)
        normalised[prefix] = parsed
        normalised[raw_key] = kept_raw
        warnings.extend(date_warnings)

    if evidence_kind == "trademark":
        _normalise_class_numbers(normalised)

    normalised["parse_warnings"] = warnings

    try:
        validated = model_cls.model_validate(normalised)
        return validated.model_dump(mode="json"), evidence_kind, schema_version
    except ValidationError as exc:
        logger.warning("Evidence validation failed for source=%s: %s", source, exc)
        warnings.append(f"ValidationError: {exc}")
        return {
            "raw_text": raw_text,
            "parse_warnings": warnings,
            "_validation_failed": True,
        }, evidence_kind, schema_version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_keys(detail: dict, field_map: Dict[str, str]) -> dict:
    """Remap scraper-produced keys to schema field names."""
    out: dict = {}
    for key, value in detail.items():
        cleaned = key.lower().strip().rstrip(":").strip()
        canonical = field_map.get(cleaned, cleaned)
        if value == "" or value is None:
            continue
        out[canonical] = value
    return out


def _normalise_class_numbers(d: dict) -> None:
    """Split class_numbers_raw into a list if it's a string."""
    raw = d.get("class_numbers_raw")
    if raw and isinstance(raw, str):
        parts = [c.strip() for c in raw.replace(",", " ").split() if c.strip()]
        d["class_numbers"] = parts if parts else None


_EXCLUSIVE_EXTRACTED_KEYS = (
    "rights_holder", "scope", "reference_number",
    "valid_from_raw", "valid_to_raw",
)


def _enrich_from_pdf_text(
    normalised: dict, raw_text: str, warnings: List[str]
) -> None:
    """Merge PDF-extracted fields into normalised dict (listing values win)."""
    from app.scrapers.dip_exclusive import extract_exclusive_rights_fields

    extracted = extract_exclusive_rights_fields(raw_text)
    extraction_warnings = extracted.pop("parse_warnings", [])
    warnings.extend(extraction_warnings)

    for key in _EXCLUSIVE_EXTRACTED_KEYS:
        if key not in normalised or normalised[key] is None:
            val = extracted.get(key)
            if val is not None:
                normalised[key] = val
