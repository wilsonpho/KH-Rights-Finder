from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://khrights:localdev@localhost:5432/khrights"
    scrape_delay_seconds: float = 2.0
    worker_poll_seconds: float = 5.0
    watchlist_check_seconds: float = 3600.0
    scraper_debug: bool = False

    model_config = {"env_file": ".env"}


settings = Settings()
