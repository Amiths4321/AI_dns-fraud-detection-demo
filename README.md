# RiskGuard — Real-Time Transaction Fraud Detection (Demo)

A working demo of an explainable, real-time fraud-detection engine for
retail banking transactions — built to showcase what a risk-scoring layer
could look like sitting on top of a core banking system like the one
DNS Bank already runs.

> **This is a sales/portfolio demo, not production software.** All
> customers, accounts, and transactions are synthetically generated.
> No real banking data is used or required.

## Why this demo, why this bank

DNS Bank has publicly invested in tech that improves loan and onboarding
turnaround time — an online KYC portal, centralised account opening, a
scorecard-based loan assessment framework, and LOS-based sanctioning — and
was recognised for it at the Cooperative Banks Top 100 Summit (Jan 2026).
This project picks up the natural next layer on top of that investment:
**transaction-level risk monitoring**, scoped specifically for how a
cooperative bank's risk team actually works:

- **Explainable, not a black box.** Every risk score comes with a
  plain-language breakdown of exactly which signals fired and how many
  points each contributed. Regulators and internal auditors can ask "why
  was this transaction blocked?" and get a real answer — not "the model
  said so."
- **Configuration, not code.** Rule weights and thresholds are constants
  in one file (`risk_engine.py`), not buried inside a trained model. A
  bank's own risk team can tune sensitivity without needing a vendor to
  redeploy anything.
- **Built for a UCB's transaction patterns**, not a generic global bank —
  amounts in INR, behavioral baselines per customer, and fraud patterns
  (round-figure mule transfers, impossible-travel transactions, sudden
  high-value transfers to new beneficiaries) that show up in Indian
  retail and SME banking specifically.

## What it does

A synthetic transaction stream is generated continuously, mimicking real
customers with stable "normal" behavior (home city, typical transaction
size, usual active hours, known beneficiaries). Each transaction is
scored against six explainable risk signals:

| Signal | What it catches |
|---|---|
| Amount deviation (z-score) | Spend far outside the customer's own historical norm |
| Odd-hour activity | Transactions outside the customer's usual active hours |
| Geo jump | Transactions far from the customer's home location |
| New beneficiary | Large transfers to a first-time recipient |
| Round-figure amount | Suspiciously round transfers, a common mule-account pattern |
| High velocity | Rapid repeat transactions on the same account |

Scores combine into a 0–100 risk level (LOW / MEDIUM / HIGH). The
dashboard shows a live feed, lets you inject any of the six fraud
patterns on demand to watch detection happen in real time, and shows the
full point-by-point explanation for any transaction you click on.

## Project structure

```
dns-fraud-detection-demo/
├── backend/
│   ├── app.py              # FastAPI app: feed, stats, fraud-injection endpoints
│   ├── risk_engine.py       # explainable scoring rules — the core IP of this demo
│   ├── data_generator.py     # synthetic customer + transaction generator
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js               # polling, live feed, charts, explainability panel
```

## Running it locally

**1. Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

**2. Frontend** (separate terminal)
```bash
cd frontend
python3 -m http.server 8080
```

Then open **http://localhost:8080** in a browser. The dashboard polls
`http://127.0.0.1:8000` by default — change the "API base" field in the
top bar if you run the backend elsewhere.

No database, no API keys, no external services required.

## Using it in a pitch

1. Open the dashboard and let the live feed run for a few seconds so it
   feels alive.
2. Click **"Impossible travel"** or **"Large amount"** to inject a fraud
   pattern live — the feed flags it immediately, the top pulse rail
   flashes, and the score chart spikes.
3. Click the flagged row and walk through the **risk breakdown panel** —
   this is the moment to make the regulatory/explainability point: every
   number is justified, nothing is a black box.
4. Point to the reasons chart to show this isn't a one-trick demo — it's
   tracking multiple distinct fraud patterns simultaneously.

## What this demo intentionally does not cover

This is scoped for a sales conversation, not a finished product. It
doesn't include: persistence/database storage, authentication, audit
logging, integration with an actual core banking system (e.g. Oracle
FLEXCUBE), case management workflow for flagged transactions, or a
trained ML model. Those are the natural "what we'd build next together"
talking points for a follow-up conversation.

## License

MIT — see `LICENSE`.
