from backend.db.db import get_conn, DB_LOCK
from typing import Dict, Optional, List
from datetime import datetime
import json


AI_DECISION_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS ai_decisions (
        id TEXT PRIMARY KEY,
        timestamp TEXT,
        symbol TEXT,
        proposed_action TEXT,
        proposed_qty REAL,
        proposed_side TEXT,
        confidence_score REAL,
        opportunity_score REAL,
        risk_score REAL,
        expected_reward REAL,
        risk_reward_ratio REAL,
        rationale TEXT,
        inputs_json TEXT,
        model_name TEXT,
        model_version TEXT,
        prompt_version TEXT,
        decision_status TEXT,
        execution_status TEXT,
        final_order_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_decision_inputs (
        id TEXT PRIMARY KEY,
        ai_decision_id TEXT,
        input_name TEXT,
        input_value TEXT,
        input_timestamp TEXT,
        FOREIGN KEY(ai_decision_id) REFERENCES ai_decisions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_decision_audit (
        id TEXT PRIMARY KEY,
        ai_decision_id TEXT,
        stage TEXT,
        passed BOOLEAN,
        reason TEXT,
        timestamp TEXT,
        FOREIGN KEY(ai_decision_id) REFERENCES ai_decisions(id)
    )
    """
]


def init_ai_db(db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        cur = conn.cursor()
        for sql in AI_DECISION_TABLES_SQL:
            cur.execute(sql)
        conn.commit()


def insert_ai_decision(decision: Dict, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            """INSERT INTO ai_decisions(id, timestamp, symbol, proposed_action, proposed_qty, 
               proposed_side, confidence_score, opportunity_score, risk_score, expected_reward,
               risk_reward_ratio, rationale, inputs_json, model_name, model_version, prompt_version,
               decision_status, execution_status, final_order_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (decision['id'], decision['timestamp'], decision['symbol'], decision['proposed_action'],
             decision.get('proposed_qty'), decision.get('proposed_side'), decision['confidence_score'],
             decision['opportunity_score'], decision['risk_score'], decision.get('expected_reward'),
             decision.get('risk_reward_ratio'), decision['rationale'], json.dumps(decision.get('inputs', {})),
             decision['model_name'], decision['model_version'], decision['prompt_version'],
             decision['decision_status'], decision.get('execution_status', 'pending'), None)
        )
        conn.commit()


def update_ai_decision_status(decision_id: str, decision_status: str, execution_status: str, 
                              order_id: Optional[str] = None, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            "UPDATE ai_decisions SET decision_status = ?, execution_status = ?, final_order_id = ? WHERE id = ?",
            (decision_status, execution_status, order_id, decision_id)
        )
        conn.commit()


def insert_ai_decision_input(decision_id: str, input_name: str, input_value: str, 
                             input_timestamp: str, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        import uuid
        input_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO ai_decision_inputs(id, ai_decision_id, input_name, input_value, input_timestamp) VALUES (?, ?, ?, ?, ?)",
            (input_id, decision_id, input_name, input_value, input_timestamp)
        )
        conn.commit()


def insert_ai_audit_log(decision_id: str, stage: str, passed: bool, reason: str, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        import uuid
        audit_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO ai_audit_log(id, ai_decision_id, stage, passed, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (audit_id, decision_id, stage, passed, reason, datetime.utcnow().isoformat())
        )
        conn.commit()


def get_ai_decision(decision_id: str, db_path: Optional[str] = None) -> Optional[Dict]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM ai_decisions WHERE id = ?', (decision_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def list_ai_decisions(limit: int = 50, db_path: Optional[str] = None) -> List[Dict]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM ai_decisions ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]

