"""Secondary source scrapers — stubs for Abacus and MISTI.

These do not affect the evidence score. Implement when
source URLs and data formats are confirmed.
"""

from __future__ import annotations

import logging

from app.scrapers.base import BaseScraper, ScraperResult, register_scraper

logger = logging.getLogger(__name__)


@register_scraper("abacus")
class AbacusScraper(BaseScraper):
    async def search(self, mark_name: str) -> list[ScraperResult]:
        logger.info("Abacus scraper not yet implemented — returning empty for '%s'", mark_name)
        return []


@register_scraper("misti")
class MISTIScraper(BaseScraper):
    async def search(self, mark_name: str) -> list[ScraperResult]:
        logger.info("MISTI scraper not yet implemented — returning empty for '%s'", mark_name)
        return []
