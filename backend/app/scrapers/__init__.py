# Import all scraper modules to trigger @register_scraper decorators
from app.scrapers import dip_trademark  # noqa: F401
from app.scrapers import dip_exclusive  # noqa: F401
from app.scrapers import secondary      # noqa: F401
