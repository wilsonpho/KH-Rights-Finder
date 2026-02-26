import pytest

import app.scrapers  # noqa: F401  — ensure registry populated
from app.scrapers.base import get_scraper, _REGISTRY


def test_registry_has_all_sources():
    assert "dip_trademark" in _REGISTRY
    assert "dip_exclusive" in _REGISTRY
    assert "abacus" in _REGISTRY
    assert "misti" in _REGISTRY


def test_get_scraper_returns_instances():
    for source in ("dip_trademark", "dip_exclusive", "abacus", "misti"):
        scraper = get_scraper(source)
        assert hasattr(scraper, "search")


def test_get_scraper_unknown_raises():
    with pytest.raises(ValueError, match="Unknown scraper source"):
        get_scraper("nonexistent")
