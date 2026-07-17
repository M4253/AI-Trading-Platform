from typing import Dict
from backend.ai_models.ai_decision_engine import decide_and_execute


def execute_trade_request(request: Dict) -> Dict:
    # This function connects higher-level API requests to the AI decision engine
    return decide_and_execute(request)
