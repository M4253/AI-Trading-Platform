from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime


class HistoricalBar:
    def __init__(self, timestamp: datetime, open_: float, high: float, low: float, close: float, volume: int, regime: str = 'neutral'):
        self.timestamp = timestamp
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.regime = regime


class DataProvider(ABC):
    """Abstract base for historical data sources. No lookahead bias."""
    
    @abstractmethod
    def get_bars(self, symbol: str, start_date: datetime, end_date: datetime) -> List[HistoricalBar]:
        """Return OHLCV bars for symbol in date range. Bars are sorted ascending by timestamp."""
        pass
    
    @abstractmethod
    def get_bar_at(self, symbol: str, timestamp: datetime) -> Optional[HistoricalBar]:
        """Return single bar at or before timestamp (point-in-time). No forward-looking."""
        pass


class CSVDataProvider(DataProvider):
    """Load historical data from CSV with columns: timestamp, open, high, low, close, volume, regime."""
    
    def __init__(self):
        self._cache: Dict[str, List[HistoricalBar]] = {}
    
    def load_csv(self, symbol: str, csv_path: str):
        """Load CSV and cache bars for symbol."""
        df = pd.read_csv(csv_path, parse_dates=['timestamp'])
        bars = []
        for _, row in df.iterrows():
            bar = HistoricalBar(
                timestamp=pd.Timestamp(row['timestamp']).to_pydatetime(),
                open_=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row.get('volume', 0)),
                regime=str(row.get('regime', 'neutral'))
            )
            bars.append(bar)
        self._cache[symbol] = sorted(bars, key=lambda x: x.timestamp)
    
    def get_bars(self, symbol: str, start_date: datetime, end_date: datetime) -> List[HistoricalBar]:
        if symbol not in self._cache:
            return []
        return [b for b in self._cache[symbol] if start_date <= b.timestamp <= end_date]
    
    def get_bar_at(self, symbol: str, timestamp: datetime) -> Optional[HistoricalBar]:
        if symbol not in self._cache:
            return None
        bars = [b for b in self._cache[symbol] if b.timestamp <= timestamp]
        return bars[-1] if bars else None

