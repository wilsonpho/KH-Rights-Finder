"""Abstract scraper interface and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScraperResult:
    title: str | None = None
    detail: dict = field(default_factory=dict)
    confidence: int | None = None
    raw_content: bytes | None = None
    content_type: str | None = None
    source_url: str | None = None


class BaseScraper(ABC):
    @abstractmethod
    async def search(self, mark_name: str) -> list[ScraperResult]:
        """Search for a mark and return evidence results."""
        ...


_REGISTRY: dict[str, type[BaseScraper]] = {}


def register_scraper(name: str):
    """Decorator to register a scraper class by source name."""
    def wrapper(cls: type[BaseScraper]):
        _REGISTRY[name] = cls
        return cls
    return wrapper


def get_scraper(source: str) -> BaseScraper:
    """Get an instantiated scraper by source name."""
    cls = _REGISTRY.get(source)
    if cls is None:
        raise ValueError(f"Unknown scraper source: {source}")
    return cls()
