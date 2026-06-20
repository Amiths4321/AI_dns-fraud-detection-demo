"""
app.py
------
FastAPI backend for the fraud-detection demo.

Endpoints:
  GET  /api/transactions?limit=50   -> most recent scored transactions
  GET  /api/stats                   -> aggregate counters for the dashboard cards
  POST /api/simulate/{kind}         -> inject a specific fraud pattern on demand
                                        kind in: large_amount, odd_hour, geo_jump,
                                        new_beneficiary, round_amount, high_velocity
  GET  /api/health                  -> simple liveness check

Run with:
  uvicorn app:app --reload --port 8000
"""

from collections import deque
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from data_generator import TransactionGenerator
from risk_engine import score_transaction

app = FastAPI(title="DNS Bank Fraud Detection Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only — lock this down to the bank's actual domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

generator = TransactionGenerator(n_customers=40, seed=None)
_lock = Lock()
FEED = deque(maxlen=200)
STATS = {"total": 0, "high": 0, "medium": 0, "low": 0, "value_flagged": 0.0}

VALID_FRAUD_KINDS = {
    "large_amount", "odd_hour", "geo_jump",
    "new_beneficiary", "round_amount", "high_velocity",
}


def _ingest(force_fraud: str | None = None) -> dict:
    txn = generator.next_transaction(force_fraud=force_fraud)
    result = score_transaction(txn)

    record = {
        "txn_id": txn["txn_id"],
        "customer_name": txn["customer_name"],
        "account_no": txn["account_no"],
        "amount": txn["amount"],
        "currency": txn["currency"],
        "category": txn["category"],
        "city": txn["city"],
        "timestamp": txn["timestamp"],
        "beneficiary": txn["beneficiary"],
        "risk_score": result["risk_score"],
        "risk_level": result["risk_level"],
        "reasons": result["reasons"],
        "injected": force_fraud is not None,
    }

    with _lock:
        FEED.appendleft(record)
        STATS["total"] += 1
        STATS[record["risk_level"].lower()] += 1
        if record["risk_level"] != "LOW":
            STATS["value_flagged"] += record["amount"]

    return record


# Seed the feed with some history so the dashboard isn't empty on first load
for _ in range(35):
    _ingest()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/transactions")
def get_transactions(limit: int = 50):
    with _lock:
        items = list(FEED)[: max(1, min(limit, 200))]
    return {"items": items}


@app.get("/api/stats")
def get_stats():
    with _lock:
        return dict(STATS)


@app.post("/api/simulate/{kind}")
def simulate(kind: str):
    if kind not in VALID_FRAUD_KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(VALID_FRAUD_KINDS)}")
    record = _ingest(force_fraud=kind)
    return record


@app.post("/api/tick")
def tick():
    """Advance the simulated feed by one organic transaction. The frontend
    polls this on an interval to keep the live feed moving."""
    record = _ingest()
    return record
