from typing import Optional

class Settings:
    """Runtime safety settings.

    IBKR connectivity is intentionally unavailable in this build.  In
    particular, no environment variable can opt the application into live
    trading: a separate, verified go-live change is required before that code
    can exist.
    """

    LIVE_TRADING: bool = False
    IB_HOST: str = '127.0.0.1'
    IB_PORT: int = 7497
    IB_CLIENT_ID: int = 1
    IB_PAPER: bool = True
    DB_PATH: Optional[str] = None

settings = Settings()
