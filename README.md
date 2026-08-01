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
| **Content moderation** | Every listing and message goes through a rule-based Turkish-aware checker: clear violations are rejected (422), borderline text is published but marked `is_flagged` and lands in the admin review queue. An optional AI layer runs only when `ANTHROPIC_API_KEY` is set and can only make the verdict stricter, never looser. |
| **Reporting** | Users can report a listing, a user or a message with a fixed reason list. Reports land in an admin-only queue where they are resolved with a note; the same target can't be reported twice by the same user, and the reporter is never shown to the person they reported. |
| **Admin moderation panel** | `/admin` — dashboard counters, the report queue, the flagged-content queue, the removed-content queue and user suspension. Access is decided solely by membership in `ADMIN_EMAILS`; every `/api/admin/*` endpoint enforces it server-side. See below for which actions can be undone. |
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
app/reports.py    user reports + admin guard (require_admin)
app/admin.py      moderation panel endpoints (/api/admin/*)
app/uploads.py    photo upload + static serving
app/pricing.py    feature engineering (shared by training & serving)
app/indexing.py   CPI (TÜFE) indexing of model output
app/emailer.py    OTP email via Brevo
scripts/          offline: train_model, build_market_values, fetch_transit, seed_demo
```

## 🛡️ Moderation & the admin panel

Two things feed one review queue: the rule-based checker marks borderline
listings and messages `is_flagged`, and users file reports. Both land in the
admin panel at `/admin`, backed by `/api/admin/*`.

**Who can get in.** An account is an admin if — and only if — its email is
listed in `ADMIN_EMAILS`. There is no separate role, admin password or second
factor. Endpoints are guarded on the server (`require_admin`: 401 without a
session, 403 for a normal account); hiding the navigation entry is not the
protection. An admin reviewing a flagged or reported message sees its
plaintext — only that message, never the surrounding conversation, and only as
long as the key it was encrypted with still exists.

**Reversibility.** No moderation action deletes anything: each one flips a flag
that a matching restore flips back. (Rows really disappear in one place only —
`DELETE /api/auth/me`, where a user erases their own account along with its
listings, messages, matches and reports.) Action by action:

- **Suspending a user** — unsuspending restores the account and its listings,
  which are hidden rather than deactivated. Suspension also ends the user's
  active sessions.
- **Resolving a report** — it can be reopened into the queue, which also clears
  the note, decider and timestamp of the reverted decision.
- **Taking a listing down** — `is_active` goes to `False`, so the listing
  leaves search, the owner's own list and its detail URL; it stays visible to
  admins in the removed queue, and `restore` returns it to the publish state it
  had at the moment of removal.
- **Removing a message** — the row stays so the conversation keeps its order,
  and the original text is *moved* aside rather than overwritten, so restoring
  writes that saved value back unchanged.

Restore only reverses an admin's removal: anything not marked as admin-removed,
such as a listing its owner closed, is refused with 400. It undoes the removal
rather than forcing content online — a listing the owner had already closed
before the takedown stays closed, and the response reports the resulting
`is_active`. A removed message's text can still fail to come back in two cases:
if `MESSAGE_KEY` was lost or replaced in the meantime the restored row decrypts
to a placeholder, and messages removed before the original-text column existed
have no saved text at all — restoring one clears the removal flag but leaves
the marker in place, drops the row out of the removed queue and cannot be
repeated.

Deployment-side settings — in particular why `DEV_OTP` must be `0` in
production before any of this can be trusted — are in
[DEPLOY.md](DEPLOY.md) sections 1.3 and 1.4.

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
DEPLOY.md explains what each one does and what happens when it is missing. Two
of them fail unsafely if ignored:

- `MESSAGE_KEY` — message encryption silently falls back to plain text when it
  is unset, and messages already encrypted with a key become unreadable if that
  key is lost.
- `DEV_OTP` — its code-level default is `1`, which returns the sign-in code in
  the API response. On a public deployment that means anyone can sign in as any
  address without a password, admin addresses included, so `render.yaml` pins
  it to `0` and DEPLOY.md section 1.3 has a check to confirm it.

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
- Enforcement is entirely manual: an admin reads the queue and acts. Nothing is
  suspended or taken down automatically, and there is no appeal flow for the
  person on the receiving end.
- Moderation removals are reversible, with two gaps: a message encrypted under
  a `MESSAGE_KEY` that has since been lost stays unreadable no matter how often
  it is restored, and messages removed before the original-text column was
  added have no saved text at all — restoring one clears the removal flag but
  leaves the marker text in place and takes the row out of the removed queue.
  Undoing keeps no history either: reopening a report or lifting a suspension
  clears the reverted decision instead of recording it.
- Admin rights are granted purely by email address (`ADMIN_EMAILS`), with no
  second factor; the safety of the whole panel rests on those accounts and on
  `DEV_OTP=0` in production.
