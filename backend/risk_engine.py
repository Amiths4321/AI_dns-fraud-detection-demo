"""
risk_engine.py
--------------
An explainable risk-scoring engine for transaction-level fraud detection.

Design intent (this matters for the bank pitch): every score this engine
produces comes with a human-readable breakdown of exactly which signals
fired and how much each contributed. Banks and their regulators are wary of
black-box ML scores they can't justify to an auditor or a customer who
disputes a blocked transaction — so explainability is treated as a first
-class output, not an afterthought.

Each rule returns (points, reason). Points are summed into a 0-100 risk
score. This is intentionally simple and inspectable rather than a opaque
trained model, which is what makes it auditable and easy to tune branch by
branch.
"""

from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

# Rule weights are tunable per the bank's own risk appetite — exposed here
# as plain constants rather than buried in a model.
WEIGHTS = {
    "amount_zscore": 35,
    "odd_hour": 20,
    "geo_jump": 30,
    "new_beneficiary": 15,
    "round_amount": 10,
    "high_velocity": 25,
}

HIGH_RISK_THRESHOLD = 60
MEDIUM_RISK_THRESHOLD = 30


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def score_transaction(txn: dict) -> dict:
    profile = txn["_profile"]
    reasons = []
    score = 0

    # 1. Amount vs customer's historical norm (z-score)
    std = max(profile["std_amount"], 1.0)
    z = (txn["amount"] - profile["avg_amount"]) / std
    if z > 3:
        pts = min(WEIGHTS["amount_zscore"], int(WEIGHTS["amount_zscore"] * (z / 6)))
        score += pts
        reasons.append({
            "code": "AMOUNT_ZSCORE",
            "label": "Unusually large amount for this customer",
            "detail": f"₹{txn['amount']:,.0f} is {z:.1f}× the customer's normal deviation "
                      f"(avg ₹{profile['avg_amount']:,.0f})",
            "points": pts,
        })

    # 2. Odd hour activity
    txn_hour = datetime.fromisoformat(txn["timestamp"]).hour
    start, end = profile["usual_hours"]
    if not (start <= txn_hour <= end):
        if txn_hour in (0, 1, 2, 3, 4):
            pts = WEIGHTS["odd_hour"]
            score += pts
            reasons.append({
                "code": "ODD_HOUR",
                "label": "Transaction at an unusual hour",
                "detail": f"Occurred at {txn_hour:02d}:00, outside customer's usual "
                          f"{start:02d}:00–{end:02d}:00 activity window",
                "points": pts,
            })

    # 3. Geo jump — far from home city, especially combined with low time gap
    dist = _haversine_km(profile["home_lat"], profile["home_lon"], txn["lat"], txn["lon"])
    if dist > 800:
        pts = WEIGHTS["geo_jump"]
        score += pts
        reasons.append({
            "code": "GEO_JUMP",
            "label": "Transaction far from customer's home location",
            "detail": f"{dist:,.0f} km from {profile['home_city']} (txn city: {txn['city']})",
            "points": pts,
        })

    # 4. New / unrecognized beneficiary on a large transfer
    if txn.get("is_new_beneficiary") and txn["amount"] > profile["avg_amount"] * 1.5:
        pts = WEIGHTS["new_beneficiary"]
        score += pts
        reasons.append({
            "code": "NEW_BENEFICIARY",
            "label": "Large transfer to a first-time beneficiary",
            "detail": f"{txn['beneficiary']} has no prior transaction history with this account",
            "points": pts,
        })

    # 5. Suspiciously round amount (common in laundering / mule transfers)
    if txn["amount"] >= 10000 and txn["amount"] % 10000 == 0:
        pts = WEIGHTS["round_amount"]
        score += pts
        reasons.append({
            "code": "ROUND_AMOUNT",
            "label": "Suspiciously round transaction amount",
            "detail": f"₹{txn['amount']:,.0f} is an exact round figure, a common mule-transfer pattern",
            "points": pts,
        })

    # 6. High velocity — repeat activity within a very short window
    if txn["seconds_since_last_txn"] is not None and 0 <= txn["seconds_since_last_txn"] < 120:
        pts = WEIGHTS["high_velocity"]
        score += pts
        reasons.append({
            "code": "HIGH_VELOCITY",
            "label": "Rapid repeat transaction",
            "detail": f"Only {txn['seconds_since_last_txn']:.0f}s since this account's last transaction",
            "points": pts,
        })

    score = min(100, score)
    if score >= HIGH_RISK_THRESHOLD:
        level = "HIGH"
    elif score >= MEDIUM_RISK_THRESHOLD:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "risk_score": score,
        "risk_level": level,
        "reasons": sorted(reasons, key=lambda r: -r["points"]),
    }
