# RoomMatch — Istanbul Roommate Platform 🏙️

A data-driven roommate matching platform for university students in Istanbul.
It combines a swipe-based matching UI with a machine-learning **fair rent
advisor**, a **budget heatmap** of 968 neighborhoods, and rail-network-based
**alternative district suggestions** — all in one app.

**Live:** https://evdes.tr
**API:** https://api.evdes.tr ([docs](https://api.evdes.tr/docs))
---

## ✨ Features

| Feature | How it works |
|---|---|
| **Sign up / login** | Email + one-time code (OTP). Passwords stored with scrypt; OTPs and session tokens stored as SHA-256 hashes. Real emails via Brevo. |
| **Listings** | Two types: *house listing* (have a room, need a roommate) and *personal listing* (need a room). Stored in SQLite/Postgres with photo upload (5 MB, JPEG/PNG/WebP). |
| **Filters** | The deck can be narrowed by district, listing type and amenities — furnished, elevator, parking, internet/heating included, balcony, natural gas. Amenity filters apply to house listings; personal listings are out of their scope rather than filtered out. |
| **Fair rent advisor** | LightGBM quantile regression predicts a fair **range** (q25–q75) for the whole flat, then derives the **per-room share** — because listers rent out one room, not the flat. Estimates are indexed to today with monthly CPI (TÜFE). |
| **Budget heatmap** | 968 neighborhood polygons colored green/yellow/red for a given budget; Turkish-aware address matching links polygons to price data. |
| **Alternative districts** | Transfer-weighted shortest paths over the rail network (station = 1, transfer = +5) suggest affordable neighborhoods near an expensive target — network cost, not straight-line distance (the Bosphorus problem). *Currently disabled in the UI pending output-quality tuning; the API and module remain.* |
| **Swipe & match** | Swipes are persisted; a match is created on mutual like, or when a lister accepts from the "Likes" queue. |
| **Chat** | Per-match messaging (participants only), 4-second polling. Messages are encrypted at rest (see below). |
| **Content moderation** | Every listing and message goes through a rule-based Turkish-aware checker: clear violations are rejected (422), borderline text is published but marked `is_flagged` in the database (there is no review screen for those rows yet). An optional AI layer runs only when `ANTHROPIC_API_KEY` is set and can only make the verdict stricter, never looser. |
| **Reporting** | Users can report a listing, a user or a message with a fixed reason list. Reports land in an admin-only queue (`ADMIN_EMAILS`) where they are marked resolved; the same target can't be reported twice by the same user. |
| **Message encryption** | Chat messages are stored AES-256-GCM encrypted (`MESSAGE_KEY`, base64 of 32 bytes) and decrypted on read. This is **at-rest** encryption, not end-to-end — the server holds the key. Without the key the app still runs, but messages are stored as plain text. |
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
app/crypto.py     AES-256-GCM encryption of message rows (MESSAGE_KEY)
app/moderation.py rule-based content checks (always on, no network)
app/moderation_ai.py  optional AI moderation layer (ANTHROPIC_API_KEY)
app/reports.py    user reports + admin review queue
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

**Tests:** `python -m pytest tests/` (backend) · `npm test` (frontend).

## 🚀 Deployment

See [DEPLOY.md](DEPLOY.md). Short version: Render builds `backend/Dockerfile`
(the model is trained during the image build) with a free Postgres via the
root `render.yaml` blueprint; Vercel serves `frontend/` with `VITE_API_URL`
pointing at the API. A GitHub Actions job pings the API every 10 minutes to
keep the free instance awake.

Backend environment variables: `DATABASE_URL`, `CORS_ORIGINS`, `DEV_OTP`,
`MESSAGE_KEY`, `ANTHROPIC_API_KEY`, `BREVO_API_KEY`, `EMAIL_FROM`,
`EMAIL_FROM_NAME`, `ADMIN_EMAILS`, `UPLOADS_DIR`, `RENT_INDEX_FACTOR`.
DEPLOY.md explains what each one does and what happens when it is missing —
`MESSAGE_KEY` in particular, because message encryption silently falls back to
plain text when it is unset, and messages already encrypted with a key become
unreadable if that key is lost.

## ⚠️ Limitations

- Model estimates are not appraisals; the listing dataset reflects early-2026
  prices (CPI-indexed forward, which tracks inflation but not micro-market
  shifts).
- Transit graph covers rail only (no metrobus/bus/ferry).
- Uploaded photos live on local disk — moving to S3/R2 is planned before real
  scale.
- Rate limiting covers the auth endpoints only (5 requests per 15 minutes per
  email address) and is kept in process memory, so it resets on restart and is
  not shared across instances. Session tokens expire after 30 days.
- Moderation is rule-based, so it is bypassable by design: obfuscated spellings
  can slip through, and unusual but innocent wording can be blocked. The
  optional AI layer narrows the gap but is off unless an API key is configured,
  and when it is on, listing and message text is sent to a third-party API.
- Message encryption protects data at rest only — it is not end-to-end, since
  the server holds the key and therefore can read messages. If `MESSAGE_KEY` is
  not configured, messages are stored in plain text.
- Reports are reviewed manually by admins; there is no automated enforcement
  (no suspensions, no takedown queue beyond marking a report resolved).
