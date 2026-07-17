import os
from typing import Optional

class Settings:
    # Toggle live trading; default False for safety
    LIVE_TRADING: bool = os.getenv('LIVE_TRADING', 'false').lower() in ('1', 'true', 'yes')
    # IBKR connection settings
    IB_HOST: str = os.getenv('IB_HOST', '127.0.0.1')
    IB_PORT: int = int(os.getenv('IB_PORT', '7497'))
    IB_CLIENT_ID: int = int(os.getenv('IB_CLIENT_ID', '1'))
    # Paper trading for IB (if connecting to paper gateway)
    IB_PAPER: bool = os.getenv('IB_PAPER', 'true').lower() in ('1', 'true', 'yes')
    # Database path override
    DB_PATH: Optional[str] = os.getenv('DB_PATH')

settings = Settings()
