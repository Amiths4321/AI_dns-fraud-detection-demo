"""
data_generator.py
------------------
Generates a synthetic population of bank customers, each with a stable
"normal" behavioral profile (home city, typical transaction size, usual
beneficiaries, typical active hours). The generator then emits a continuous
stream of transactions that mostly match each customer's normal profile,
occasionally producing transactions that deviate from it.

This mimics real core-banking transaction logs closely enough to demo a
risk engine without touching any real customer data.
"""

import random
import string
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

CITIES = [
    ("Dombivli", 19.2167, 73.0833),
    ("Thane", 19.2183, 72.9781),
    ("Mumbai", 19.0760, 72.8777),
    ("Kalyan", 19.2403, 73.1305),
    ("Pune", 18.5204, 73.8567),
    ("Nashik", 19.9975, 73.7898),
    ("Ujjain", 23.1765, 75.7885),
    ("Indore", 22.7196, 75.8577),
]

FAR_CITIES = [
    ("Dubai", 25.2048, 55.2708),
    ("Singapore", 1.3521, 103.8198),
    ("London", 51.5072, -0.1276),
    ("Lagos", 6.5244, 3.3792),
]

FIRST_NAMES = ["Rohan", "Priya", "Sanjay", "Anita", "Vikram", "Sunita", "Aniket",
               "Kavita", "Suresh", "Meera", "Rajesh", "Pooja", "Nitin", "Sneha"]
LAST_NAMES = ["Patil", "Joshi", "Deshmukh", "Kulkarni", "Shah", "Naik", "Pawar",
              "Bhosale", "Gokhale", "Rane"]

MERCHANT_CATS = ["Grocery", "Utility Bill", "ATM Withdrawal", "Fund Transfer",
                  "E-commerce", "Fuel", "Medical", "Education Fee", "Rent",
                  "Insurance Premium"]


def _account_no():
    return "DNS" + "".join(random.choices(string.digits, k=10))


@dataclass
class Customer:
    customer_id: str
    name: str
    account_no: str
    home_city: str
    home_lat: float
    home_lon: float
    avg_amount: float
    std_amount: float
    usual_hours: tuple  # (start_hour, end_hour) most activity happens in this window
    known_beneficiaries: list = field(default_factory=list)
    last_txn_time: datetime = field(default_factory=datetime.utcnow)
    last_txn_city: str = ""


class TransactionGenerator:
    def __init__(self, n_customers: int = 40, seed: int | None = None):
        if seed is not None:
            random.seed(seed)
        self.customers = [self._make_customer() for _ in range(n_customers)]

    def _make_customer(self) -> Customer:
        city, lat, lon = random.choice(CITIES)
        avg = round(random.uniform(800, 45000), 2)
        cust = Customer(
            customer_id=str(uuid.uuid4())[:8],
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            account_no=_account_no(),
            home_city=city,
            home_lat=lat,
            home_lon=lon,
            avg_amount=avg,
            std_amount=round(avg * 0.25, 2),
            usual_hours=(random.choice([7, 8, 9, 10]), random.choice([19, 20, 21, 22])),
        )
        cust.known_beneficiaries = [
            "Beneficiary-" + "".join(random.choices(string.digits, k=4))
            for _ in range(random.randint(2, 5))
        ]
        cust.last_txn_city = city
        return cust

    def _normal_transaction(self, cust: Customer, now: datetime) -> dict:
        amount = max(50, round(random.gauss(cust.avg_amount, cust.std_amount), 2))
        hour = random.randint(cust.usual_hours[0], cust.usual_hours[1])
        txn_time = now.replace(hour=hour % 24, minute=random.randint(0, 59))
        beneficiary = random.choice(cust.known_beneficiaries + [None])
        city, lat, lon = cust.home_city, cust.home_lat, cust.home_lon

        return self._build(cust, amount, txn_time, city, lat, lon, beneficiary, forced_anomaly=None)

    def _anomalous_transaction(self, cust: Customer, now: datetime, kind: str | None = None) -> dict:
        kind = kind or random.choice([
            "large_amount", "odd_hour", "geo_jump", "new_beneficiary",
            "round_amount", "high_velocity",
        ])

        amount = cust.avg_amount
        hour = random.randint(cust.usual_hours[0], cust.usual_hours[1])
        city, lat, lon = cust.home_city, cust.home_lat, cust.home_lon
        beneficiary = random.choice(cust.known_beneficiaries)
        txn_time = now

        if kind == "large_amount":
            amount = round(cust.avg_amount * random.uniform(6, 15), 2)
        elif kind == "odd_hour":
            hour = random.choice([0, 1, 2, 3, 4])
            txn_time = now.replace(hour=hour, minute=random.randint(0, 59))
        elif kind == "geo_jump":
            city, lat, lon = random.choice(FAR_CITIES)
            amount = round(cust.avg_amount * random.uniform(1, 3), 2)
        elif kind == "new_beneficiary":
            beneficiary = "Beneficiary-" + "".join(random.choices(string.digits, k=4))
            amount = round(cust.avg_amount * random.uniform(2, 5), 2)
        elif kind == "round_amount":
            amount = float(random.choice([50000, 100000, 200000, 250000, 500000]))
        elif kind == "high_velocity":
            amount = round(cust.avg_amount * random.uniform(0.8, 1.5), 2)
            txn_time = cust.last_txn_time + timedelta(seconds=random.randint(5, 90))

        return self._build(cust, amount, txn_time, city, lat, lon, beneficiary, forced_anomaly=kind)

    def _build(self, cust, amount, txn_time, city, lat, lon, beneficiary, forced_anomaly):
        txn = {
            "txn_id": str(uuid.uuid4()),
            "customer_id": cust.customer_id,
            "customer_name": cust.name,
            "account_no": cust.account_no,
            "amount": round(amount, 2),
            "currency": "INR",
            "category": random.choice(MERCHANT_CATS),
            "timestamp": txn_time.isoformat(),
            "city": city,
            "lat": lat,
            "lon": lon,
            "beneficiary": beneficiary,
            "is_new_beneficiary": beneficiary not in cust.known_beneficiaries,
            "seconds_since_last_txn": (txn_time - cust.last_txn_time).total_seconds(),
            "_forced_anomaly": forced_anomaly,  # used only for demo labeling, not shown to the risk engine
            # profile snapshot needed by the risk engine to score this txn relative to the customer's norm
            "_profile": {
                "avg_amount": cust.avg_amount,
                "std_amount": cust.std_amount,
                "home_city": cust.home_city,
                "home_lat": cust.home_lat,
                "home_lon": cust.home_lon,
                "usual_hours": cust.usual_hours,
                "known_beneficiaries": list(cust.known_beneficiaries),
                "last_txn_city": cust.last_txn_city,
            },
        }
        cust.last_txn_time = txn_time
        cust.last_txn_city = city
        if beneficiary and beneficiary not in cust.known_beneficiaries and random.random() < 0.3:
            cust.known_beneficiaries.append(beneficiary)
        return txn

    def next_transaction(self, force_fraud: str | None = None) -> dict:
        cust = random.choice(self.customers)
        now = datetime.utcnow()
        if force_fraud:
            return self._anomalous_transaction(cust, now, kind=force_fraud)
        # ~6% of organic traffic is anomalous, mimicking a realistic fraud rate
        if random.random() < 0.06:
            return self._anomalous_transaction(cust, now)
        return self._normal_transaction(cust, now)
