# RoomMatch — Istanbul Roommate Platform 🏙️

A data-driven roommate matching platform for university students in Istanbul.
It combines a swipe-based matching UI with a machine-learning **fair rent
advisor**, a **budget heatmap** of 968 neighbourhoods, moderation and reporting
with an admin review queue, and rail-network-based **alternative district
suggestions** — all in one app, in Turkish and English.

**Live:** https://evdes.tr
**API:** https://api.evdes.tr (interactive docs are off in production; run the
API locally with `API_DOCS=1` to see them)

---

## ✨ Features

| Feature | How it works |
|---|---|
| **Sign up / login** | Email + one-time code (OTP), or email + password. Registration requires a university address — any `.edu.tr` domain, plus the few known university domains that are not `.edu.tr` (`sabanciuniv.edu`, listed in `backend/app/universities.py`) — enforced on the server; the form mirrors the same rule (a test keeps the two lists equal). Addresses in `ADMIN_EMAILS` are exempt. Signing in does **not** re-check the domain: the rule decides who may open an account, not who may return to one. Passwords are stored with scrypt, session tokens as SHA-256 hashes, OTPs as HMAC-SHA256 keyed by `OTP_KEY`. Real emails via Brevo. |
| **Listings** | Two types: *house listing* (have a room, need a roommate) and *personal listing* (need a room). District is required and neighbourhood optional — with one, the fair-price estimate is computed for that neighbourhood instead of the district as a whole. Three photos minimum (5 MB each, JPEG/PNG/WebP). Every upload is re-encoded: EXIF (GPS position, device, date) and other metadata are dropped and the long edge is capped at 2048 px. |
| **Location picker** | 38 districts and 539 neighbourhoods served from `/api/locations`, filtered to the names the price model recognises so no choice is offered that cannot be priced. Search ignores Turkish diacritics — *besiktas* finds *Beşiktaş*. |
| **Interface language** | Turkish and English, switchable at any time. Turkish is the source language; a missing English key falls back to it rather than rendering blank. Numbers and dates follow the selected locale. Server messages (errors, moderation rejections) follow it too: the frontend sends the selected language as `Accept-Language` and the API answers in it, Turkish when the header is absent. |
| **Filters** | The deck can be narrowed by district (several at once), listing type, price, rooms, amenities — furnished, elevator, parking, internet/heating included, balcony, natural gas — and lifestyle: non-smoking and pet-friendly (the house rules on house listings), and the poster's own alcohol and sleep answers. Filters only use what the card already shows; an unknown answer does not match. Amenity filters apply to house listings; personal listings are out of their scope rather than filtered out. There is no gender filter: listings do not record who lives there yet, and the owner's gender is not shown. |
| **Fair rent advisor** | LightGBM quantile regression predicts a fair **range** (q25–q75) for the whole flat, then derives the **per-room share** — because listers rent out one room, not the flat. Estimates are indexed to today with the central bank's monthly new-tenant rent index for İstanbul (TCMB YKKE). |
| **Budget heatmap** | 968 neighbourhood polygons coloured green/yellow/red for a given budget; Turkish-aware address matching links polygons to price data. Prices carry the same rent indexing as the advisor, so the two features quote the same month. Neighbourhoods resting on fewer than 8 listings are drawn faded — coloured, but marked as a weak signal. |
| **Alternative districts** | Transfer-weighted shortest paths over the rail network (station = 1, transfer = +5) suggest affordable neighborhoods near an expensive target — network cost, not straight-line distance (the Bosphorus problem). Shown in the map's neighbourhood panel when a cheaper neighbourhood within about 45 minutes by rail fits the budget. |
| **Swipe & match** | Swipes are persisted; a match is created on mutual like, or when a lister accepts from the "Likes" queue. |
| **Chat** | Per-match messaging (participants only), 4-second polling. Messages are encrypted at rest (see below). |
| **Content moderation** | Every listing and message goes through a rule-based Turkish-aware checker: clear violations are rejected (422), borderline text is published but marked `is_flagged` and lands in the admin review queue. Listings with one of the two strong scam patterns (an IBAN with urgency or a deposit, or a deposit before viewing) are held out of the deck until an admin approves them. An optional AI layer runs only when `ANTHROPIC_API_KEY` is set and can only make the verdict stricter, never looser. |
| **Reporting** | Users can report a listing, a user or a message with a fixed reason list. Reports land in an admin-only queue where they are resolved with a note; the same target can't be reported twice by the same user, and the reporter is never shown to the person they reported. |
| **Admin moderation panel** | `/admin` — dashboard counters, the report queue, the flagged-content queue, the removed-content queue, user search and suspension, and an audit log of irreversible actions. Admins can also edit, publish, take down or permanently delete any listing, and delete any account. Access is decided solely by membership in `ADMIN_EMAILS` (environment only, no default); all 15 `/api/admin/*` endpoints enforce it server-side, on the router and on each route. Admin accounts sign in with password **and** an emailed code. See below for which actions can be undone. |
| **Message encryption** | Chat messages are stored AES-256-GCM encrypted (`MESSAGE_KEY`) and decrypted on read. This is **at-rest** encryption, not end-to-end — the server holds the key. Without the key the app still runs, but messages are stored as plain text. |
| **Abuse limits** | Per-user quotas on the content endpoints: 20 listings/hour, 30 messages/minute, 10 reports/hour, 100 photo uploads/day. Auth endpoints are limited per email *and* per IP, and a successful sign-in clears the counter so a stranger cannot lock someone out of their own account. |
| **Theming** | Hinge-inspired layout with a campus notebook language: student ID cards, ruled paper for what people write, graph paper for what the model computes, a highlighter for the key number. Light "notebook" and dark "blackboard" themes (default light). |

## 📚 Documentation

Long-form engineering documentation lives in [`docs/`](docs/) — architecture,
the fair-rent model, the non-ML algorithms, the frontend, and a security audit.
[`docs/README.md`](docs/README.md) says which document answers which question
and in what order to read them. Deployment is [DEPLOY.md](DEPLOY.md). The
optional AWS service for the fair-rent model (S3, Lambda, API Gateway,
Terraform, least-privilege CI deploys) is [`docs/AWS.md`](docs/AWS.md).

## 🧠 Models & method

Details in [`docs/MODEL.md`](docs/MODEL.md). Summary:

- **Fair rent (module 1):** target `log(rent)`; LightGBM quantile regression
  (q25/q50/q75) yields an interval instead of a point estimate. The served
  model's median error is **15.3%** against a ~25% neighbourhood-median
  baseline. Outputs are **indexed** from the training period (2025-02) to
  the present with TCMB's new-tenant rent index for İstanbul: its February 2026
  annual change, then one monthly change per bulletin (`app/indexing.py`).
  That index replaced TÜİK's CPI housing group in October 2026, because CPI
  rent tracks sitting tenants, whose rents have been catching up after the
  legal cap ended and so ran well ahead of new-tenant rents.
- **Budget heatmap (module 2):** ~600 B per request (geometry downloaded once
  and cached client-side).
- **Alternative districts (module 3):** rail network from
  OpenStreetMap/Overpass (ODbL).

## 🏗️ Architecture

```
frontend/            React + TypeScript + Vite + Tailwind + shadcn/ui  →  Vercel
backend/             FastAPI + SQLAlchemy + LightGBM (Docker)          →  Render
                     SQLite locally, Postgres in production
services/fairprice/  fair-rent model inference (container image)       →  AWS Lambda (optional)
infra/               Terraform: S3, ECR, Lambda, API Gateway, IAM, CloudWatch
```

With AWS configured, the backend asks the Lambda for the price band and falls
back to its in-process model on any error or timeout; models are trained in
GitHub Actions, gated on quality and versioned in S3 ([`docs/AWS.md`](docs/AWS.md)).

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
app/uploads.py    photo upload + static serving
app/pricing.py    feature engineering (shared by training, backend & Lambda)
app/rent_model.py where the model comes from (S3 or image) and who computes the band (Lambda or local)
app/indexing.py   rent index (TCMB YKKE İstanbul) applied to model output
app/admin.py      admin panel endpoints (/api/admin/*)
app/locations.py  district -> neighbourhood list, filtered to model coverage
app/content_limits.py  per-user quotas on content endpoints
app/migrate.py    additive schema migration + drift warning on startup
app/emailer.py    OTP email via Brevo
scripts/          offline: train_model, publish_model (S3 + quality gate),
                  build_market_values, fetch_transit
```

## 🛡️ Moderation & the admin panel

Two things feed one review queue: the rule-based checker marks borderline
listings and messages `is_flagged`, and users file reports. Both land in the
admin panel at `/admin`, backed by `/api/admin/*`.

**Who can get in.** An account is an admin if — and only if — its email is
listed in `ADMIN_EMAILS`, which is read from the environment only — the code
has no default and the production API does not start without it. There is no
separate role, but an admin signs in with two factors: the password opens no
session on its own, it sends a code to the admin's inbox, and the session
opens once that code is entered (the "Kodla gir" tab asks for the password
after the code). Endpoints are guarded on the server (`require_admin`: 401
without a session, 403 for a normal account); hiding the navigation entry is
not the protection. An admin reviewing a flagged or reported message sees its
plaintext — only that message, never the surrounding conversation, and only as
long as the key it was encrypted with still exists.

**Reversibility.** Moderation actions are reversible; administration is not.
The review queue only ever flips flags that a matching restore flips back. The
owner's tools — permanent listing deletion and account deletion — really do
remove rows, ask for a written reason and are recorded in the audit log, which
outlives the admin who acted (deleting their account nulls the reference rather
than erasing the entry). Users can also erase their own account through
`DELETE /api/auth/me`, which takes its listings, messages, matches, reports and
uploaded photo files with it. It accepts the password or a fresh e-mail code,
and a forgotten password can be reset with a code (`POST /api/auth/reset-password`),
so neither right depends on remembering the password.

Deleting a listing keeps the conversation it started: its swipes and the reports
about it go, but matches survive with `listing_id` set to null. The listing was
why two people began talking, not something they own together.

Action by action:

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

Restore only reverses an admin's removal: anything not marked as admin-removed
is refused with 400. It undoes the removal rather than forcing content online —
a listing the owner had already closed before the takedown stays closed, and
the response reports the resulting `is_active`. Putting such a listing back on
the market is a separate, deliberate act: `POST /api/admin/listings/{id}/publish`,
which refuses (409) anything an admin removed so the two paths cannot write the
same field under different rules. A removed message's text can still fail to come back in two cases:
if `MESSAGE_KEY` was lost or replaced in the meantime the restored row decrypts
to a placeholder, and messages removed before the original-text column existed
have no saved text at all — restoring one clears the removal flag but leaves
the marker in place, drops the row out of the removed queue and cannot be
repeated.

**Two limits stay in place.** An admin can suspend or delete neither themselves
nor another admin. Admin rights come only from `ADMIN_EMAILS`, so the last admin
locking themselves out would leave the platform with no way back in; this
protects the owner from their own slip rather than withholding authority. Their
own account is still deletable the ordinary way, behind a password. There is
also no "sign in as this user": reviewing reported content is one thing, reading
someone's private conversations as them is another.

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
DEV_OTP=1 python -m app.main
```

`DEV_OTP=1` returns the sign-in code in the API response and the app shows it
in a toast, so you can register without an email provider. It is off unless
set, and must stay off on any public deployment (DEPLOY.md section 1.3). To use
the admin panel locally, also set `ADMIN_EMAILS=you@uni.edu.tr` (any address
you register with); nobody is an admin otherwise.

On macOS, LightGBM needs: `brew install libomp`. Transit data ships with the
repo; re-download with `python -m scripts.fetch_transit` if needed. The
interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are off by default,
production included; start the API with `API_DOCS=1` as well to see them.
`requirements.txt` pins every package to an exact version; to add or upgrade
one, edit `requirements.in` and regenerate the lock with the command at the
top of that file.

**2) Frontend** (http://localhost:8080)

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_URL defaults to 127.0.0.1:8000
npm run dev
```

**Tests:** `python -m pytest tests/` (backend, 436) · `npm test` (frontend,
88) · `npm run typecheck` · `npm run lint`. GitHub Actions runs all of them,
plus `npm run build`, on every pull request and every push to `main`
(`.github/workflows/ci.yml`); Render deploys a `main` commit only after they
pass, and the frontend goes to Vercel production only after that backend is
live (`.github/workflows/frontend-deploy.yml`, DEPLOY.md §2.1).

## 🚀 Deployment

See [DEPLOY.md](DEPLOY.md). Short version: Render builds `backend/Dockerfile`
(the model is trained during the image build) from the root `render.yaml`
blueprint, against a free Neon Postgres, with uploaded photos in a Cloudflare
R2 bucket; Vercel serves `frontend/` with `VITE_API_URL` pointing at the API. An external uptime monitor pings `https://api.evdes.tr/`
every 5 minutes to keep the free instance awake — see DEPLOY.md for why this is
not a GitHub Actions cron.

Backend environment variables: `DATABASE_URL`, `CORS_ORIGINS`, `DEV_OTP`,
`MESSAGE_KEY`, `OTP_KEY`, `PUBLIC_BASE_URL`, `TRUST_PROXY_HEADERS`,
`ANTHROPIC_API_KEY`, `BREVO_API_KEY`, `EMAIL_FROM`, `EMAIL_FROM_NAME`,
`ADMIN_EMAILS`, `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY`, `S3_REGION`, `UPLOADS_DIR`, `RENT_INDEX_FACTOR`,
`MAX_REQUEST_BYTES`, `EXTRA_PHOTO_HOSTS`, `API_DOCS`. DEPLOY.md explains what each one does and what happens
when it is missing. Several fail *quietly* rather than loudly, which is the
dangerous kind:

- `MESSAGE_KEY` — message encryption silently falls back to plain text when it
  is unset, and messages already encrypted with a key become unreadable if that
  key is lost.
- `DEV_OTP` — off unless set. Set to `1`, it returns the sign-in code in the
  API response; on a public deployment that means anyone can sign in as any
  address without a password, admin addresses included. `render.yaml` pins it
  to `0`, and DEPLOY.md section 1.3 has a check to confirm it.
- `OTP_KEY` — without it, OTP codes are stored as unsalted SHA-256. Six digits
  is a search space of a million, so anyone who reads the database recovers a
  live code in seconds.
- `TRUST_PROXY_HEADERS` — behind a reverse proxy the real client IP only exists
  in `X-Forwarded-For`. Left off, every request looks like it comes from the
  proxy and the IP-keyed limits protect nothing. Left on *without* a proxy in
  front, the header is client-controlled and the limits are just as useless.
- `PUBLIC_BASE_URL` — the base for uploaded-photo URLs. Unset, it falls back to
  the request's `Host` header, which the client chooses.
- `S3_BUCKET` — unset, photos are written to the container disk, which Render's
  free plan wipes on every redeploy and every sleep. The app keeps running and
  only the startup log says so (DEPLOY.md section 1.5).

## ⚠️ Limitations

- Model estimates are not appraisals. The dataset is from **February 2025** and
  carries no date column — the period comes from how it was collected, not from
  the data. Indexing forward tracks inflation, not micro-market shifts, and the
  multiplier itself is an estimate within published bounds (see `app/indexing.py`).
- Transit graph covers rail only (no metrobus/bus/ferry).
- Uploaded photos live in a Cloudflare R2 bucket and are served through the API
  at `/uploads/<name>`, so they load only while the API is up. Photos are
  public — the URL is unguessable but needs no session.
- Rate limits are kept in process memory, so they reset on restart and are not
  shared across instances; with more than one worker the real ceiling is the
  configured limit times the worker count. Photo upload is capped at 100 a day
  per account, which bounds what one account can add to the paid bucket.
  Session tokens expire after 30 days.
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
- Admin rights are granted purely by email address (`ADMIN_EMAILS`). Admin
  sign-in takes the password and an emailed code, so the second factor is the
  admin's mailbox; there are no roles and no authenticator-app option.
- `.edu.tr` proves the address belongs to a university, not that the person
  behind it is currently a student — the domain outlives graduation and says
  nothing about who is reading the mailbox.
- Registration still answers whether an address is already registered (409),
  which is an enumeration signal. It is kept because hiding it would make the
  sign-up flow worse; the per-IP limit is what makes scanning expensive.
- Images are not moderated at all. Text is checked on every listing and message;
  photos pass through untouched.
- The full audit and what remains open is in [`docs/SECURITY.md`](docs/SECURITY.md).
