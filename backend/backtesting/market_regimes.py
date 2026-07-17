from dataclasses import dataclass
from enum import Enum


class RegimeType(Enum):
    BULL = 'bull'
    BEAR = 'bear'
    SIDEWAYS = 'sideways'
    CRASH = 'crash'
    HIGH_VOLATILITY = 'high_vol'
    LOW_VOLATILITY = 'low_vol'
    NEUTRAL = 'neutral'


@dataclass
class RegimeDefinition:
    regime_type: RegimeType
    description: str
    volatility_threshold: float
    trend_strength: float  # positive for bull, negative for bear


REGIME_DEFINITIONS = {
    RegimeType.BULL: RegimeDefinition(RegimeType.BULL, 'Bull market', 0.5, 0.7),
    RegimeType.BEAR: RegimeDefinition(RegimeType.BEAR, 'Bear market', 0.5, -0.7),
    RegimeType.SIDEWAYS: RegimeDefinition(RegimeType.SIDEWAYS, 'Sideways range', 0.3, 0.0),
    RegimeType.CRASH: RegimeDefinition(RegimeType.CRASH, 'Market crash', 2.0, -0.9),
    RegimeType.HIGH_VOLATILITY: RegimeDefinition(RegimeType.HIGH_VOLATILITY, 'High volatility', 2.0, 0.0),
    RegimeType.LOW_VOLATILITY: RegimeDefinition(RegimeType.LOW_VOLATILITY, 'Low volatility', 0.1, 0.0),
}

