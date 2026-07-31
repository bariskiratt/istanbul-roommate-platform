# RoomMatch — Istanbul Roommate Platform 🏙️

A data-driven roommate matching platform for university students in Istanbul.
It combines a swipe-based matching UI with a machine-learning **fair rent
advisor**, a **budget heatmap** of 968 neighborhoods, and rail-network-based
**alternative district suggestions** — all in one app.

**Live demo:** https://istanbul-roommate-platform.vercel.app
**API:** https://roommatch-api-4ack.onrender.com ([docs](https://roommatch-api-4ack.onrender.com/docs))

> **Attribution:** the UI (`frontend/`) originates from
> [mirzemirsat/roommate-finder-plus](https://github.com/mirzemirsat/roommate-finder-plus).
> This monorepo integrates it with a Python/FastAPI model backend and a full
> persistence layer.

---

## ✨ Features

| Feature | How it works |
|---|---|
| **Sign up / login** | Email + one-time code (OTP). Passwords stored with scrypt; OTPs and session tokens stored as SHA-256 hashes. Real emails via Brevo. |
| **Listings** | Two types: *house listing* (have a room, need a roommate) and *personal listing* (need a room). Stored in SQLite/Postgres with photo upload (5 MB, JPEG/PNG/WebP). |
| **Fair rent advisor** | LightGBM quantile regression predicts a fair **range** (q25–q75) for the whole flat, then derives the **per-room share** — because listers rent out one room, not the flat. Estimates are indexed to today with monthly CPI (TÜFE). |
| **Budget heatmap** | 968 neighborhood polygons colored green/yellow/red for a given budget; Turkish-aware address matching links polygons to price data. |
| **Alternative districts** | Transfer-weighted shortest paths over the rail network (station = 1, transfer = +5) suggest affordable neighborhoods near an expensive target — network cost, not straight-line distance (the Bosphorus problem). |
| **Swipe & match** | Swipes are persisted; a match is created on mutual like, or when a lister accepts from the "Likes" queue. |
| **Chat** | Per-match messaging (participants only), 4-second polling. |
| **Theming** | Hinge-inspired editorial design; light & dark themes (default dark). |

## 🧠 Models & method

Details in `backend/README.md`. Summary:

- **Fair rent (module 1):** target `log(rent)`; LightGBM quantile regression
  (q25/q50/q75) yields an interval instead of a point estimate. 5-fold CV
  median error **15.1%** vs. a 25% neighborhood-median baseline. Outputs are
  **CPI-indexed** from the training period (2026-01) to the current month
  (`app/indexing.py` — add one line per month as TÜİK publishes).
- **Budget heatmap (module 2):** ~600 B per request (geometry downloaded once
  and cached client-side).
- **Alternative districts (module 3):** rail network from
  OpenStreetMap/Overpass (ODbL).

## 🏗️ Architecture

```
frontend/   React + TypeScript + Vite + Tailwind + shadcn/ui  →  Vercel
backend/    FastAPI + SQLAlchemy + LightGBM (Docker)          →  Render
            SQLite locally, Postgres in production
```

Key backend modules:

```
app/main.py       API wiring, model/heatmap/transit endpoints
app/auth.py       register / OTP / sessions (Bearer tokens)
app/listings.py   listing CRUD with ownership
app/swipes.py     swipes, likes queue, matches
app/messages.py   per-match chat
app/uploads.py    photo upload + static serving
app/pricing.py    feature engineering (shared by training & serving)
app/indexing.py   CPI (TÜFE) indexing of model output
app/emailer.py    OTP email via Brevo
scripts/          offline: train_model, build_market_values, fetch_transit, seed_demo
```

## ▶️ Running locally (two terminals)

**1) Backend** (http://127.0.0.1:8000)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python -m scripts.train_model   # trains the fair-rent model (~1 min, first time)
python -m app.main
```

On macOS, LightGBM needs: `brew install libomp`. Transit data ships with the
repo; re-download with `python -m scripts.fetch_transit` if needed.

**2) Frontend** (http://localhost:8080)

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_URL defaults to 127.0.0.1:8000
npm run dev
```

Optional demo content (20 users + 100 realistic listings, rents derived from
real neighborhood medians): `python -m scripts.seed_demo`.

**Tests:** `python -m pytest tests/` (backend, 38 tests) · `npm test` (frontend).

## 🚀 Deployment

See [DEPLOY.md](DEPLOY.md). Short version: Render builds `backend/Dockerfile`
(the model is trained during the image build) with a free Postgres via the
root `render.yaml` blueprint; Vercel serves `frontend/` with `VITE_API_URL`
pointing at the API. A GitHub Actions job pings the API every 10 minutes to
keep the free instance awake.

Backend environment variables: `DATABASE_URL`, `CORS_ORIGINS`, `DEV_OTP`,
`BREVO_API_KEY`, `EMAIL_FROM`, `UPLOADS_DIR`, `RENT_INDEX_FACTOR`.

## ⚠️ Limitations

- Model estimates are not appraisals; the listing dataset reflects early-2026
  prices (CPI-indexed forward, which tracks inflation but not micro-market
  shifts).
- Transit graph covers rail only (no metrobus/bus/ferry).
- Uploaded photos live on local disk — moving to S3/R2 is planned before real
  scale.
- No rate limiting or token expiry yet; the landing-page showcase cards are
  decorative.
