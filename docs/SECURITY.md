# Security

This document describes the security model of the RoomMatch / evdes.tr platform
and the results of an adversarial audit of it.

It is written for an engineer who knows software but has never read this
codebase. Each section starts with the *problem* the mechanism exists to solve,
then explains *how* the mechanism works, and only then points at the code. Every
claim carries a `file:line` reference so you can check it yourself — this
project has repeatedly shipped documentation and UI copy that promised things
the code did not do. The audit in section 10 found two such places (**H5** and
**H6**); both have since been fixed in code.

**Status as of 10 October 2026.** The audit ran against commit `51e5bb4`. Most
findings were fixed in `dfd79b8`, the commit that added this document, and in
later commits. Section 10 opens with a table of where each finding stands now,
and the rest of the document describes the current code. The finding write-ups
in section 10 are kept as they were found, so their line numbers point at
`51e5bb4` (read them with `git show 51e5bb4:<path>`); every other reference
points at the code as of this update. Line numbers drift with every change: if
one is off, search for the function it names.

**Nothing here was tested against production (`api.evdes.tr`).** All exploitation
was reproduced against a throwaway local instance on `127.0.0.1:8377` with an
isolated SQLite database, and the status review was done by reading the code
and running its tests. Where a finding depends on production configuration
that could not be read without touching production, it is labelled as such in
section 11.

---

## 1. What is being protected

| Asset | Where it lives | Why an attacker wants it |
|---|---|---|
| Student identity (name, university, department, year) | `users` table, `backend/app/models.py:24` | Social engineering, targeting a specific person |
| Private chat messages | `messages.content`, encrypted at rest (`backend/app/models.py:234`) | Rental-deposit scams, harassment, doxxing |
| Uploaded photos (faces, apartments) | Cloudflare R2 bucket (private), served publicly by the API at `/uploads/<name>` (`serve_photo`, `backend/app/uploads.py`) | Re-identification, harassment, reuse in fake listings |
| Session tokens | `auth_tokens.token_hash` (`backend/app/models.py:89`) | Account takeover |
| Admin capability | Derived purely from email membership (`backend/app/models.py:83`) | Full moderation control: read flagged private messages, permanently delete accounts |
| Service availability | Render free tier, single container, Neon free Postgres | Extortion, sabotage, or simple vandalism |

---

## 2. Threat model

The realistic adversaries for a student housing platform, ordered by how likely
they are to actually show up:

### 2.1 The scammer (most likely)

Posts an attractive room below market rate, moves the conversation to WhatsApp,
asks for a deposit by bank transfer, disappears. This is the single most common
real-world attack on roommate platforms in Turkey, and it is what the fair-rent
advisor and the `dolandiricilik` (fraud) moderation category exist for.

**Defences:** rule-based moderation flags fraud patterns
(`backend/app/moderation.py:677`), optional AI layer
(`backend/app/moderation_ai.py:80`), user reporting
(`backend/app/reports.py:143`), admin suspension
(`backend/app/admin.py:1311`), and the fair-price estimate that makes a
suspiciously cheap listing visibly suspicious.

**Not defended:** identity is an email address, not a person. Nothing ties an
account to a real human. A banned scammer re-registers in thirty seconds with
any other university address they control. Since the **H5** fix the server at
least insists on a university address (`StudentEmailIn`,
`backend/app/auth.py:431-460`); before it, any address worked.

### 2.2 The harasser

Uses matching as a channel to reach a specific student. The product design
limits this structurally: messaging only opens after a *mutual* like
(`backend/app/messages.py:50`, `_require_participant`), so there is no
unsolicited-message surface at all. Reporting a message is available
(`backend/app/reports.py:143`) and the admin can overwrite the text with a
sentinel while keeping the row (`backend/app/admin.py:759`).

**Not defended:** there is no user-level block/mute. The only remedies are
report → admin suspension, or account deletion.

### 2.3 The spammer / bulk-content attacker

Wants to publish many listings or messages cheaply. This is the threat the audit
found the platform least prepared for: findings **H2** and **H3** together let a
single account write unbounded amounts of data through an endpoint that is then
served to every anonymous visitor. Both are fixed: every stored list element
has a length cap, and listings, messages, reports, comments on likes and
photo uploads are rate-limited per account
(`backend/app/content_limits.py:25-44`). The counters
live in process memory (section 4.5).

### 2.4 The scraper

Wants the student roster: who is on the platform, from which university, in
which district. Two separate leaks fed this. Anonymous `GET /api/listings` no
longer returns the owner's name and university (**L3**, fixed). The auth
endpoints still partly answer "is this address registered?" (**M3**):
`request-otp` now gives the same answer either way, but `register` still returns
409 for a taken address. Combined with the predictable
`ad.soyad@ogr.university.edu.tr` pattern used by Turkish universities, this was
a real enumeration path; at 10 registration attempts per IP per hour
(`backend/app/auth.py:72-73`) it is now a slow one.

Logged-in callers see a little more about a listing's owner than anonymous
ones: `owner_profile` carries the department, year, sleep schedule, the
smoking/pets/alcohol answers and the first profile photo, because the deck
shows them as profile cards (`Listing.owner_profile`, `backend/app/models.py`;
hidden by `_hide_owner` in `backend/app/listings.py`). Anonymous callers get
`null`. Budget, preferred districts and the bio are deliberately left out:
they stay visible only to someone the person liked or matched.

### 2.5 The account-takeover attacker

Wants someone else's session. The high-value target is not a student account but
an address in `ADMIN_EMAILS` (`backend/app/config.py`), because admin rights
are *derived from the email string alone* — there is no separate role column
(`backend/app/models.py:83`). Two things now raise the bar: the list comes only
from the environment (the repository no longer names the admin addresses), and
an admin session needs the password **and** an emailed code together
(`_start_admin_second_factor` / `_require_admin_password` in
`backend/app/auth.py`). Controlling the mailbox alone, or knowing the password
alone, no longer yields moderation power.

### 2.6 The vandal (denial of service)

Wants the site down. On a free-tier Render container with 512 MB of RAM, this
was cheap: **H1** (unbounded request bodies), **H2** (unbounded stored payloads)
and **M1** (locking a specific user out of their own account with five
requests). H1 and H2 are fixed; M1 is partly fixed, and section 10 says what
is left of it.

### Explicitly out of scope

Nation-state adversaries, physical access to Render's infrastructure, malicious
Render/Brevo/Anthropic insiders, and compromise of the operator's own laptop.
The at-rest message encryption (section 7) is deliberately *not* a defence
against a compromised application server; it defends against a leaked database
dump.

---

## 3. Trust boundaries

```mermaid
flowchart LR
    subgraph client["Browser (untrusted)"]
        UI["React SPA<br/>token in localStorage<br/>frontend/src/lib/api.ts:18"]
    end

    subgraph vercel["Vercel (static hosting)"]
        SPA["evdes.tr<br/>vercel.json = SPA rewrite + security headers"]
    end

    subgraph render["Render container (trust anchor)"]
        API["FastAPI<br/>backend/app/main.py:365"]
        STATIC["/uploads/* photos<br/>uploads.py:527 serve_photo — NO auth"]
        KEY["MESSAGE_KEY in env<br/>render.yaml"]
    end

    subgraph data["Data at rest"]
        PG[("Postgres<br/>messages encrypted<br/>AES-256-GCM")]
        DISK[["Cloudflare R2 bucket<br/>photo files"]]
    end

    subgraph third["Third parties"]
        BREVO["Brevo<br/>OTP emails"]
        ANTH["Anthropic<br/>optional moderation"]
    end

    UI -->|HTTPS + Bearer| API
    UI --> SPA
    API --> PG
    API --> DISK
    STATIC -.->|public, unauthenticated| UI
    API -->|email + 6-digit code| BREVO
    API -->|full listing / message text| ANTH
    KEY --- API
```

The single trust anchor is the Render container. It holds the message
decryption key, so "encrypted messages" means *encrypted against a database
leak*, not against the server itself. Photos at `/uploads/<name>` are outside
every authorization check by design: `serve_photo`
(`backend/app/uploads.py:524-527`) hands the file to anyone who has its URL.
The name is 16 random bytes, so the URL cannot be guessed, but it never
expires.

---

## 4. Identity

### 4.1 The `.edu.tr` restriction — the product's central promise

The whole trust proposition is "verified Istanbul university students". The
mechanism that enforces it is a domain restriction on sign-up.

**What exists:** a rule on the server's registration schema. `RegisterIn`
inherits from `StudentEmailIn`, whose validator rejects any address that is not
a student address:

```
backend/app/auth.py:375-400   is_student_email
  domain == "edu.tr" or domain.endswith(".edu.tr"), or a domain in
  app/universities.py DOMAINS (sabanciuniv.edu is a university but not .edu.tr)
backend/app/auth.py:431-460   class StudentEmailIn._normalize
  if v in config.ADMIN_EMAILS: return v
  if not is_student_email(v): raise ValueError(STUDENT_EMAIL_ERROR)
```

The onboarding form keeps its own check as a form hint
(`frontend/src/pages/Onboarding.tsx:124`). Until the **H5** fix that hint was
the only check, and `curl` skipped it: `attacker@gmail.com` registered,
verified, and then carried out the rest of the audit session.

Two edges are deliberate:

- **Only sign-up is restricted.** Login, `request-otp` and `verify-otp` use the
  plain `EmailIn` (`backend/app/auth.py:409-428`). Its docstring records why:
  when the rule also guarded login, accounts opened earlier with other
  addresses were locked out of themselves in production.
- **`ADMIN_EMAILS` is exempt** (`backend/app/auth.py:455-456`). One admin
  address is not a university address, and admin rights hang on the address.
  The list comes from an environment variable only the operator sets.

The university name shown on a profile is derived from the email domain
(`backend/app/universities.py:10` `DOMAINS`, applied at
`backend/app/auth.py:670`) and cannot be edited by the user — `UserUpdate`
deliberately omits the field (`backend/app/auth.py:528`).

**Stops:** anyone without a university address from opening an account,
including someone who skips the form and calls the API directly.
**Does not stop:** a student lending their address, or one person holding
several; the domain is checked, not the person (section 13, item 1).

### 4.2 OTP (one-time code)

Registration issues a 6-digit code; the account is not `verified` until the code
comes back.

- Generated with a CSPRNG: `secrets.randbelow(1_000_000)`, `backend/app/auth.py:338`.
- Stored as `HMAC-SHA256(OTP_KEY, code)` (`_issue_otp` → `_otp_digest`,
  `backend/app/auth.py:314-319`), with a 10-minute TTL (`OTP_TTL`,
  `backend/app/auth.py:41`). `OTP_KEY` is a server environment variable that
  `render.yaml` generates, so the stored value is useless without it. Without
  `OTP_KEY`, or with one shorter than 32 characters, storage falls back to an
  unsalted SHA-256 and the process prints a warning once
  (`backend/app/auth.py:289-311`) — but in production (`DATABASE_URL` set) the
  app refuses to start in that state rather than run with the weak hash
  (`backend/app/startup_checks.py`).
- Compared with `hmac.compare_digest` (`_otp_matches`,
  `backend/app/auth.py:322-334`) — constant time, so no timing oracle on the
  code itself.
- Single use: cleared on success (`backend/app/auth.py:806-808`).
- Brute force is bounded by the rate limiter: 5 attempts per 15 minutes
  (`backend/app/auth.py:55-56`), against a 10⁶ space.

**Stops:** using an email address you do not control; online brute force of the
code.
**Does not stop:** someone who holds both the database and the server
environment. With `OTP_KEY` set, a leaked dump or log line no longer reveals a
live code (**M2**, fixed); without it, the unsalted hash over a 10⁶ space
inverts in under a second.

There is a development escape hatch: when `DEV_OTP=1`, the code is returned *in
the API response* (`backend/app/auth.py:344-352`, `:368-369`). It is off unless
the variable is set: local development turns it on by hand
(`backend/README.md`), and `render.yaml` still pins `DEV_OTP: "0"` for
production. Until the **L6** fix the code default was `"1"`, so a deployment
that did not use this blueprint returned codes to anyone who asked.

### 4.3 Passwords

- Hashed with `scrypt`, N=2¹⁴, r=8, p=1, 16-byte random salt per password:
  `backend/app/auth.py:47`, `:224-230`.
- Verified in constant time via `hmac.compare_digest`, `backend/app/auth.py:238`.
- Policy is length only: minimum 8 characters, maximum 128
  (`backend/app/auth.py:463`). No complexity rule, no breached-password check.
- Changing the password invalidates every session
  (`backend/app/auth.py:906-908`) — a real logout-everywhere, not just the
  current device.

**Stops:** offline cracking of a leaked hash at any meaningful rate for a decent
password.
**Does not stop:** credential stuffing with a password the student already
reused elsewhere. N=2¹⁴ is also below the current OWASP recommendation of 2¹⁷
(**L6**).

### 4.4 Session tokens

- Opaque 256-bit random string, `secrets.token_urlsafe(32)`,
  `backend/app/auth.py:721`.
- Only the SHA-256 hash is stored (`backend/app/models.py:89`,
  `backend/app/auth.py:722`) — a database leak does not yield usable sessions.
  Plain SHA-256 is correct here and not a weakness, because the input is already
  256 bits of entropy; there is nothing to brute-force.
- 30-day TTL, enforced on read and the expired row deleted
  (`TOKEN_TTL`, `backend/app/auth.py:42`, `:605-611`).
- Suspension deletes all of a user's tokens (`backend/app/admin.py:1336-1338`),
  and `get_optional_user` re-checks `is_suspended` on every request as a second
  gate (`backend/app/auth.py:616-617`) in case a row survives.
- Logout deletes the single token (`backend/app/auth.py:1136-1148`).

**Stops:** stale sessions surviving a suspension or a password change; session
recovery from a database dump.
**Does not stop:** theft from the browser. The token lives in `localStorage`
(`frontend/src/lib/api.ts:16-20`), which is readable by any script that achieves
XSS. There is no HttpOnly cookie. What stands in the way is the site's
Content-Security-Policy, which runs scripts only from the site's own origin
(`script-src 'self'`, `frontend/vercel.json:78`); it was added for **M5**.

### 4.5 Rate limiting

Two in-memory counters, both sliding windows.

**Auth endpoints** use `_rate_limit` (`backend/app/auth.py:125-142`), with the
key chosen per endpoint:

| Endpoint | Key | Limit | Where |
|---|---|---|---|
| `register` | email | 5 per 15 min | `backend/app/auth.py:639` |
| `register` | IP | 10 per hour | `:640-645` |
| `request-otp` | email | 5 per 15 min | `:702` |
| `request-otp` | IP | 15 per hour | `:705` |
| `login` | email + IP, cleared on success | 5 per 15 min | `:752`, `:770` |
| `verify-otp` | email, cleared on success | 5 per 15 min | `:788`, `:812` |

Stale buckets are pruned and the table is capped at 10,000 keys
(`backend/app/auth.py:87-113`).

**Content endpoints** use `content_limits.check`, keyed by user id
(`backend/app/content_limits.py:25-44`): 20 listings an hour, 30 messages a
minute, 10 reports an hour, 30 comments on likes an hour, 100 photo uploads a
day. A like without a comment is not counted.

**Stops:** online brute force of one account's password or OTP; bulk
registration and address scanning from one IP; one account flooding listings,
messages, reports or the photo bucket (**H3**, fixed).
**Does not stop:**
- An attacker with many IP addresses: each gets its own registration and login
  allowance.
- The code path being turned against its owner: five `request-otp` or bad
  `verify-otp` calls from anyone block that address's code sign-in for 15
  minutes. The email-only key on `verify-otp` is a choice — with an IP in it, a
  botnet could search the 10⁶ code space in parallel
  (`backend/app/auth.py:779-787`). Password login stays open (**M1**, partly
  fixed).
- Wrong client IPs. Behind Render's proxy every request arrives from the proxy,
  so `_client_ip` reads the right-most `X-Forwarded-For` entry, and only when
  `TRUST_PROXY_HEADERS=1` (`backend/app/auth.py:150-173`; `render.yaml` sets
  it). That assumes Render is the only proxy: put a CDN proxy in front and the
  right-most entry becomes the CDN's address, shared by many users.
- Multi-process deployments. Both counters are per-process memory and reset on
  restart; the module comments say so (`backend/app/auth.py:49-54`,
  `backend/app/content_limits.py:12-15`).

---

## 5. Authorization

### 5.1 Ownership checks

Every mutation of a user-owned row re-reads the row and compares owner ids
server-side. The pattern is consistent:

| Action | Check | Code |
|---|---|---|
| Edit listing | `user.id != row.owner_id` → 403 | `backend/app/listings.py:530` |
| Deactivate listing | same | `backend/app/listings.py:591` |
| Read chat | not a participant → 404, same as a missing match (**L4**) | `backend/app/messages.py:50-63` |
| Send message | same helper | `backend/app/messages.py:112` |
| Respond to a like | like must be on *your* listing → 404 | `backend/app/swipes.py:260-264` |

Mass assignment is closed by schema design rather than by a blocklist:
`UserUpdate` (`backend/app/auth.py:528`) simply does not declare `email`,
`university`, `verified`, `is_suspended` or `id`, and Pydantic drops unknown
keys. `is_admin` cannot be assigned at all because it is a computed property,
not a column (`backend/app/models.py:83`). This was probed during the audit and
held (section 12).

### 5.2 Admin authority

Admin status is membership in a set of email addresses:

```
backend/app/models.py:83-87
    @property
    def is_admin(self) -> bool:
        from app.config import ADMIN_EMAILS
        return self.email.lower() in ADMIN_EMAILS
```

`ADMIN_EMAILS` comes only from an environment variable; there is no default in
the code, and a production boot (`DATABASE_URL` set) with an empty list stops
(`critical_problems`, `backend/app/startup_checks.py`). Enforcement is a single
dependency, `require_admin` (`backend/app/reports.py:54`), attached to the
`/api/admin` router itself and again to every route: 401 without a token, 403
with a non-admin token. The router-level copy is a backstop so a future route
that forgets the parameter is still closed (`backend/tests/test_admin_login.py`
checks every `/api/admin` route).

There is still no separate role, so the email *is* the authority. What changed
is how a session for that email is obtained: a normal account signs in with its
password or an emailed code, an admin account needs both. The correct password
sends a code (whose email warns that the password was just used) instead of
opening a session; `verify-otp` checks the password only after the code
matches, so a wrong-code probe cannot learn which addresses are admins. Email
changes are impossible by construction (`UserUpdate` has no `email` field and
no app code assigns `User.email`; both are tested), which matters because a
changeable email would be a self-service admin grant.

### 5.3 Protected boundaries, and why they exist

Two operations — suspend and permanent delete — refuse to act on the acting
admin or on any other admin:

```
backend/app/admin.py:1226-1252   _protect_admin_accounts
    if target.id == admin.id:  400
    if target.is_admin:        403
```

The docstring is explicit that this is a **safety interlock, not a permission
boundary**. The reasoning: there is no endpoint that can un-suspend or restore
the last admin, because reaching that endpoint requires being an admin. A single
click would irreversibly destroy platform governance. The same argument extends
to admin-on-admin actions: if two admins could delete each other, one
compromised mailbox would be enough to wipe the moderation team.

Crucially, this does not remove anyone's right to delete their own account.
`DELETE /api/auth/me` remains open to admins and requires the password
(`backend/app/auth.py:1114-1133`). What is blocked is the accidental,
one-click-plus-reason-box path — not the deliberate, authenticated one.

There is also a deliberate *absence*: no impersonation endpoint. The reasoning
is written down at `backend/app/admin.py:45-49` — an admin can already see
reported and flagged content, but taking over a session to read private chats or
write in someone's name is a categorically different power. If the need ever
arises, the correct answer is a read-only viewer.

### 5.4 Ordering rule that is easy to get wrong

`_protect_admin_accounts` checks "is it me" *before* "is the target an admin",
because the admin is themselves an admin and the checks would otherwise return
the wrong status code and the wrong message (`backend/app/admin.py:1244-1247`).
Small, but it is the kind of ordering bug that makes an error message lie.

---

## 6. Content safety

### 6.1 Layer 1 — rules, always on

`backend/app/moderation.py` is a pure, dependency-free, Turkish-aware text
checker. Its design bias is stated up front (`backend/app/moderation.py:6-10`):
this is a rental listing site, so **wrongly blocking an innocent listing is
worse than missing a rude word**. Therefore `block` is produced only for
unambiguous profanity, hate speech and sexual harassment; everything heuristic
(fraud suspicion, contact details, off-platform redirection) produces at most
`flag`.

The hard part is Turkish false positives — "sıkıntı", "ışık", "amaç", "mal" all
collide with profanity stems once Turkish characters are folded. Four mitigations
are documented and implemented at `backend/app/moderation.py:14-36`: word-boundary
matching instead of substring scanning, separate folded/unfolded passes for short
colliding stems, an explicit `_SAFE_TOKENS` allowlist, and no short English stems
at all. Evasion handling (zero-width characters, Cyrillic/Greek homoglyphs,
leetspeak, space removal) is described in the same block.

Thresholds: `BLOCK_THRESHOLD = 1.0`, `FLAG_THRESHOLD = 0.4`, and the fraud
category is capped at `_SCAM_MAX = 0.9` so that it can *never* block on its own
(`backend/app/moderation.py:66-73`).

Enforcement points: listings check title and description separately so the error
can name the offending field (`backend/app/listings.py:100-132`); messages check
the body (`backend/app/messages.py:141-149`); a comment on a like is checked as
a message (`_prepare_comment`, `backend/app/swipes.py:171-200`). Blocked content
returns 422; flagged content is published with `is_flagged=True` and lands in
the admin queue. A flagged comment keeps its flag on the swipe row and passes
it to the chat message it becomes on a match, which is where the queue sees
it. Until then the only reader is the listing owner it was written to.

### 6.2 Layer 2 — AI, optional and strictly-additive

`backend/app/moderation_ai.py` sends the text to Anthropic's API
(`claude-haiku-4-5`, `:38`) for classification. Three properties make this safe
to bolt on:

1. **Off by default.** It runs only if `ANTHROPIC_API_KEY` is set
   (`backend/app/moderation.py:711-713`).
2. **Never blocking on failure.** Timeout (5 s, `moderation_ai.py:42`), network
   error or malformed JSON all yield `None`, and the caller silently falls back
   to the rule result (`backend/app/moderation.py:704-720`).
3. **Can only tighten.** Results are combined with `merge`, where the stricter
   verdict wins and reasons are unioned (`backend/app/moderation.py:725`). The
   AI cannot un-block something the rules blocked; in fact the rules short-circuit
   before calling it when they already said `block`
   (`backend/app/moderation.py:702-703`).

### 6.3 Reporting

Users report a listing, a user or a message from a closed reason list
(`backend/app/reports.py:26-42`). Reporting requires a login — the docstring at
`backend/app/reports.py:148` says why: to close the anonymous-report-flood
surface. The same user cannot report the same target twice, enforced both by a
pre-check and by a database `UniqueConstraint`, with the race losing side turned
into a 409 rather than a 500 (`backend/app/models.py:326-329`,
`backend/app/reports.py:173-185`).

The reporter must also be able to see the target (`_reportable`,
`backend/app/reports.py:76-110`, called at `:156`): a message only by a
participant of its match, a listing only while it is public, a user only while
not suspended. Anything else gets the same 404 as an id that does not exist.
Before the **H4** fix, any account could push someone else's private message
into the moderation queue by its id. Reports are also capped at 10 an hour per
account (`backend/app/reports.py:154`).

### 6.4 Admin queue

The queue is built around a set of principles written out at the top of the
module (`backend/app/admin.py:1-56`). They are numbered there; the numbering is
kept here so the two can be read side by side. Principle 3b (no impersonation)
is covered in section 5.3 and principle 4 (every action is recorded) in
section 9.

- **1 — Reversible first.** Suspend rather than delete, hide rather than erase.
  Removed content stays findable at `GET /api/admin/flagged?status=removed`, a
  message's text is moved to `original_content` rather than overwritten, and
  restore endpoints exist for both listings and messages.
  *Honest exception, documented in the same block:* messages removed before
  those columns existed genuinely lost their text; restore returns
  `restored:false` and deliberately leaves the flag up so the record stays
  findable.
- **1b — Destructive paths exist, but separate and logged.** `DELETE
  /api/admin/listings/{id}` and `DELETE /api/admin/users/{id}` require a
  reason, write an `AdminAction`, and — importantly — *conversations survive*:
  deleting a listing NULLs `matches.listing_id` rather than deleting the chat
  (`purge_listing`, `backend/app/listings.py:171-221`).
- **2 — The reporter is never shown to the reported.** These endpoints are
  admin-only and reporter identity does not leak out of them. See **L1** for
  the one place where this principle leaks in the opposite direction.
- **3 — The admin sees only what the decision requires.** A reported message
  returns *that message*, not the conversation
  (`backend/app/admin.py:375-388`). The user list returns email addresses only
  for suspended accounts (`backend/app/admin.py:1202-1225`), and email is
  searchable (`?q=`) without being returned — "find this address" does not
  require seeing all addresses.

The `?q=` search escapes LIKE wildcards (`backend/app/admin.py:479-487`),
otherwise a `%` search would quietly return the whole table and the admin would
believe they had found what they searched for.

---

## 7. Cryptography

### 7.1 Message encryption at rest

Chat messages are encrypted before being written and decrypted on read:

- AES-256-GCM, 12-byte random nonce per message, stored as
  `enc:v1:` + base64(nonce ‖ ciphertext ‖ tag) — `backend/app/crypto.py:145-155`.
- Decryption at `backend/app/crypto.py:157-180`; a value not starting with the
  prefix is treated as legacy plaintext and returned as-is, because production
  already contains plaintext rows from before the feature existed.
- Applied at the write path (`backend/app/messages.py:154`) and both read paths
  (`backend/app/messages.py:39-46`, `backend/app/admin.py:381`).
- Comments on likes are encrypted with the same function before they are stored
  (`backend/app/swipes.py:200`). On a match the ciphertext is copied into the
  message row unchanged, never decrypted and re-encrypted.
- A row that fails to decrypt returns the sentinel `[unreadable]`
  (`backend/app/crypto.py:51`) rather than 500-ing the whole conversation. The
  sentinel is language-independent on purpose; the UI translates it.

### 7.2 Why this is not end-to-end encryption

The key is an environment variable on the server
(`backend/app/crypto.py:83-113`). The server therefore *can* read every message,
and does — the moderation layer runs on plaintext before encryption
(`backend/app/messages.py:141`), and the admin queue decrypts reported messages
(`backend/app/admin.py:381`).

This is a deliberate trade-off, not an oversight. Real end-to-end encryption
would make server-side moderation impossible, and on a platform whose primary
threat is deposit fraud conducted *inside the chat*, losing moderation would cost
more than at-rest encryption buys. What at-rest encryption actually protects
against is narrow and worth stating precisely: **a leaked database dump or a
stolen backup.** It protects against nothing else.

The codebase enforces the honesty of this claim in three places: the module
docstring instructs that no user-facing text may say "end-to-end"
(`backend/app/crypto.py:5-8`), the messages module repeats it
(`backend/app/messages.py:6-8`), and the Safety page copy says it outright —
"the decryption key lives on the server, so anyone with access to the server can
read the messages" (`frontend/src/i18n/translations.ts:1655`, TR at `:672`).

### 7.3 Key management and the loss scenario

`MESSAGE_KEY` accepts two formats (`backend/app/crypto.py:83-120`):

1. base64 of exactly 32 bytes — the preferred form, produced by
   `python -m app.crypto --genkey`.
2. Any raw string of ≥ 32 characters, from which the key is derived with a
   single unsalted SHA-256 (`backend/app/crypto.py:111-112`).

Format 2 exists for a concrete operational reason: Render's `generateValue: true`
produces a string that is not base64-of-32-bytes, and without this branch the
blueprint's own generated key would have been silently rejected and messages
written in plaintext. The cost is that no entropy check is performed on the raw
path — see **L5**.

**The failure mode that matters:** if `MESSAGE_KEY` is absent or malformed,
encryption cannot turn on. In production (`DATABASE_URL` set) the app now
**refuses to start** instead of silently storing plaintext — a startup check
(`backend/app/startup_checks.py`) raises, so a misconfigured deploy fails and
the previous version keeps serving until the key is fixed. Locally (SQLite, no
`DATABASE_URL`) it still falls back to plaintext with a log warning
(`backend/app/crypto.py:90-94`, `:115-119`) so development is not blocked.
`render.yaml` and `DEPLOY.md §1.1` carry the operational detail.

**If the key is lost or rotated:** every message encrypted under the old key
becomes permanently unreadable and renders as `[unreadable]`. There is no key
rotation mechanism, no key versioning beyond the `v1` string in the prefix, and
no re-encryption script. `render.yaml` instructs the operator to copy the
generated value out of the dashboard and back it up after the first deploy. That
backup is the entire recovery plan.

### 7.4 Other cryptographic choices

| Use | Primitive | Location | Note |
|---|---|---|---|
| Password storage | scrypt N=2¹⁴, r=8, p=1, per-password salt | `backend/app/auth.py:47` | Below OWASP's 2¹⁷ (**L6**) |
| Session token storage | SHA-256 of a 256-bit random token | `backend/app/auth.py:220`, `:721` | Correct — input already has full entropy |
| OTP storage | HMAC-SHA256 keyed with `OTP_KEY`; unsalted SHA-256 if the key is missing | `backend/app/auth.py:314-319` | A leaked row is useless without the key (**M2**, fixed) |
| Upload filenames | `secrets.token_hex(16)` | `backend/app/uploads.py:510` | Unguessable, but public and permanent once known (section 3) |
| Message AEAD | AES-256-GCM, no AAD | `backend/app/crypto.py:153`, `:175` | Ciphertext not bound to its row (**L6**) |

---

## 8. Privacy and third parties

Brevo and, when it is switched on, Anthropic receive user data to do a job for
the app; Neon, Cloudflare R2, Render and Vercel host it (section 8.3).

### 8.1 Brevo — transactional email (always on in production)

`backend/app/emailer.py:29-77`. What is sent: the recipient's email address and
the 6-digit login code, in both the subject line and the body
(`backend/app/emailer.py:38-56`). Brevo was chosen because its free tier allows
sending to arbitrary recipients from a verified sender without domain
verification (`backend/app/emailer.py:5-8`).

Failure handling is careful about logging: when Brevo rejects a send, only the
provider's status code and error text are logged — **never the code or the
recipient** (`backend/app/emailer.py:65-69`).

Behaviour when email is unconfigured depends on `DEV_OTP`: with `DEV_OTP=0`, the
default, the request fails loudly with 502 rather than silently leaving the
user without a code (`backend/app/auth.py:362-366`).

### 8.2 Anthropic — content classification (opt-in)

`backend/app/moderation_ai.py`. Runs only when `ANTHROPIC_API_KEY` is set. What
is sent: **the full text of the listing or message being screened**, truncated
to 4000 characters (`moderation_ai.py:45`), plus a fixed system prompt. No user
id, no email, no name — just the text and a `İLAN`/`SOHBET MESAJI` label
(`_KIND_LABEL`, `moderation_ai.py:70`, interpolated into the user turn at
`:94-97`).

This is disclosed to users. The Safety page states that while the layer is on,
"the full text of the listings and messages being screened is sent to Anthropic
for classification" (`frontend/src/i18n/translations.ts:1649`, TR at `:666`).
That is an unusually honest piece of product copy and it matches the code. The
privacy notice adds that the layer is currently off and nothing is sent to an
AI provider (`frontend/src/i18n/translations.ts:1929-1930`), so setting
`ANTHROPIC_API_KEY` means updating that notice first.

### 8.3 Storage providers

Since October 2026 the database runs on Neon and uploaded photos are stored in
a private Cloudflare R2 bucket (DEPLOY.md sections 1.5 and 1.6). Both hold user
data at rest outside Turkey and are named in the privacy notice (`/privacy`,
section 4). The R2 token in `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` is
scoped to the one bucket; anyone holding it can read and delete every photo.

### 8.4 What was not disclosed

A privacy notice exists (`/privacy`, `frontend/src/pages/Privacy.tsx`, route
at `frontend/src/App.tsx:57`). It names Render, Neon, Cloudflare R2, Vercel and
Brevo, says AI moderation is off, and says data goes to no one outside that
list. Until 12 October 2026 it left out the three things below (**L6**). The
notice now names Google Fonts and OpenStreetMap in section 4 and lists what
the audit record keeps in section 6 (`privacy.shareGoogleFonts`,
`privacy.shareOsm`, `privacy.retentionAudit` in
`frontend/src/i18n/translations.ts`). Nothing about the data flows themselves
changed; self-hosting the fonts would still remove the Google one.

- **Google Fonts.** The stylesheet loads its fonts from `fonts.googleapis.com`
  (`frontend/src/index.css:3`), so every visitor's IP address reaches Google.
- **OpenStreetMap tiles.** The explore map loads tiles from
  `tile.openstreetmap.org` (`frontend/src/pages/Explore.tsx:145`), which sends
  the visitor's IP address to the OpenStreetMap Foundation.
- **What the audit trail keeps.** The notice said only the link to the user
  is severed when an admin record outlives a deleted account. In fact a user
  deletion stores the deleted account's email, name and university in the
  record (`backend/app/admin.py:1416-1422`), and a listing deletion stores the
  owner's name (`:1170-1177`).


---

## 9. Audit trail

Reversible moderation actions record their actor in their own row:
`reports.resolved_by` / `resolved_at` (`backend/app/models.py:344-346`),
`users.suspended_by` / `suspended_at` / `unsuspended_by` / `unsuspended_at`
(set at `backend/app/admin.py:1325-1329` and `:1364-1368`), and
`reviewed_by` / `reviewed_at` on listings and messages.

Irreversible actions cannot do that — the row itself disappears — so they go to a
dedicated table:

```
backend/app/models.py:270-317   class AdminAction
  actor_id     (nullable FK to users)
  action       "listing_delete" | "user_delete" | "listing_update" | "listing_publish"
  target_type  "listing" | "user"
  target_id    (Integer, deliberately NOT a foreign key — the target is gone)
  reason       (mandatory on destructive endpoints)
  detail       (JSON: what the deleted row contained, what an edit overwrote)
  created_at
```

Three design decisions worth understanding:

- **The audit row is written in the same transaction as the action**
  (`backend/app/admin.py:448-477`, `db.flush()` not `db.commit()`). If they were
  separate commits, a failed deletion could leave behind a log entry claiming a
  deletion that never happened.
- **Reversible actions are deliberately *not* written here**
  (`backend/app/admin.py:33-36`). They already carry their actor in their own
  columns, and recording the same event twice means the two records can
  eventually disagree.
- **Deleting an admin does not delete their audit trail.** `actor_id` is
  nullable and `purge_user` NULLs it rather than cascading
  (`backend/app/auth.py:1065-1079`). The comment says why: otherwise the easiest
  way to erase your own moderation history would be to delete your own account.

What is recorded on a user deletion includes the deleted account's email, name
and university (`backend/app/admin.py:1416-1422`) — necessary to answer "which
account did I delete", but it means an audit row outlives the erasure request
that produced it (**L6**). The privacy notice says so (section 8.4).

---

## 10. Audit results — verified findings

All findings below were **reproduced by execution** against a local instance
(`127.0.0.1:8377`, isolated SQLite, `DEV_OTP=1`, a single admin address), unless
the entry says otherwise. Severity reflects damage a real attacker can do to a
real user, not theoretical worst case.

### Status on 10 October 2026

The write-ups below are kept as the audit found them, at `51e5bb4`. This table
says where each finding stands in the current code, and each write-up opens
with a **Now** note on what changed and what is left.

| ID | Finding | Now | What is left |
|---|---|---|---|
| H1 | Chunked bodies bypass the size limit | Fixed | — |
| H2 | Unbounded `photos` / `preferred_districts` elements | Fixed | — |
| H3 | No rate limit on content endpoints | Fixed | Counters live in process memory (section 4.5) |
| H4 | Report endpoint as id oracle and queue injection | Fixed | — |
| H5 | `.edu.tr` checked only in the browser | Fixed | — |
| H6 | Photos survive account deletion | Fixed | Uploads never attached to anything wait 7 days for the sweep |
| M1 | Lockout DoS | Partly fixed | Code sign-in still locks per email |
| M2 | Hashes in error logs; OTP hash invertible | Fixed | — |
| M3 | Email enumeration | Partly fixed | `register` 409, suspended 403, timing |
| M4 | Upload URL from `Host`; no `nosniff` on files | Fixed | Without `PUBLIC_BASE_URL`, upload URLs still come from `Host` |
| M5 | No security headers | Fixed | Not checked against production |
| L1 | Suspension reason shown to the user | Open | — |
| L2 | `_RATE_BUCKETS` grows without bound | Fixed | — |
| L3 | Anonymous listings show owner name and university | Fixed | — |
| L4 | 404-vs-403 enumeration | Fixed | — |
| L5 | No entropy check on a raw `MESSAGE_KEY` | Open | — |
| L6 | Other hardening items | 6 of 9 fixed | See its table |

Two problems were found during the status review, not by the audit: the
DELETE gap in H1 and the cross-account photo deletion in H6. Both were
reproduced against a local instance and have since been fixed; the H1 and H6
notes say how.

### HIGH

#### H1 — Chunked uploads bypass the body-size limit → unbounded disk/memory write

> **Now: fixed.** `BodySizeLimitMiddleware`
> (`backend/app/main.py:267-360`) caps every request body at 6 MB
> (`MAX_REQUEST_BYTES`, `:247`). The headers that frame the body decide, not
> the method: a declared `Content-Length` over the cap gets 413 before the
> body is read, a chunked body is counted as it streams and cut off at the
> cap, and a request with neither has no body. Until 10 October 2026 the
> middleware waved DELETE through as bodyless, but `DELETE /api/auth/me` and
> the admin delete endpoints take a JSON body, and FastAPI reads it before it
> checks the token: an anonymous 20 MB chunked DELETE was read in full and
> answered 422. It now gets 413
> (`backend/tests/test_security_headers.py:278-308`).

**Where:** `backend/app/uploads.py:54-55` (the Content-Length check),
`backend/app/main.py` (no ASGI-level body cap anywhere).

The endpoint tries to reject oversized bodies before reading them by inspecting
the `content-length` header. A request sent with `Transfer-Encoding: chunked`
has no `content-length`, so the check never fires — and Starlette's multipart
parser has already spooled the entire part to a temporary file before the
endpoint function runs. `file.read(MAX_BYTES + 1)` at `backend/app/uploads.py:58`
therefore limits nothing that matters.

Reproduced with a raw socket, watching the server process's open temp file grow:
12.5 MB at ~3 s, 25.1 MB at ~6 s, 75.5 MB at ~18 s and still growing, before the
413 was finally returned *after the whole body hit disk*. The same unbounded
buffering applies to non-upload JSON endpoints, since Starlette reads the body
into memory.

**Impact:** one verified account with a handful of concurrent connections fills
the container's ephemeral disk and IO, or OOMs a 512 MB free-tier instance.
Service outage.

**Fix:** cap the request body at the reverse proxy (Render / Cloudflare), and
additionally stream-limit in the app via `Request.form(max_part_size=…)` or an
ASGI `receive` wrapper. A `file.read()` limit alone cannot work — parsing
finishes first.
**Effort:** medium (half a day); proxy config as a 1-hour stopgap.

#### H2 — Unbounded element length in `photos` / `preferred_districts` → stored amplification on an anonymous endpoint

> **Now: fixed.** Each listing photo must be at most 500 characters and pass
> the photo allowlist (`_check_photos`, `backend/app/listings.py:47-74`).
> Profile photos are capped at 6 × 500 characters and preferred districts at
> 10 × 40 (`backend/app/auth.py:512-525`, applied at `:566-570`). New profile
> photos pass the same allowlist; see M4.

**Where:** `backend/app/listings.py:223` (`photos: Field(..., min_length=3,
max_length=6)` constrains the *count*, not the elements),
`backend/app/auth.py:246` (`preferred_districts: list[str] | None` — no
constraint at all), `backend/app/auth.py:248` (same problem for profile photos).

Pydantic's `max_length` on a `list[str]` bounds the number of items. Nothing
bounds the length of each item, and nothing bounds the list length for
`preferred_districts`.

Reproduced:

```
POST /api/listings   photos = ["A" * 2_000_000] * 6        -> 201
anon GET /api/listings                                     -> 12,001,715 bytes
PATCH /api/auth/me   preferred_districts = ["A"*10000]*2000,
                     photos = ["x"*2_000_000]*6            -> 200
GET  /api/auth/me                                          -> 32,006,380 bytes
```

**Impact:** `GET /api/listings` is unauthenticated
(`backend/app/listings.py:325`, `get_optional_user`), so a single bloated row is
served to **every visitor**. Postgres storage and Render bandwidth are exhausted
by one attacker. Combined with H3 (no rate limit) it scales.

**Fix:** constrain per element —
`list[Annotated[str, StringConstraints(max_length=500)]]` for photo URLs;
`max_length=10` on the `preferred_districts` list plus `max_length=40` per item.
**Effort:** very low, 2–3 lines. Best impact-to-effort ratio in this report.

#### H3 — No rate limit on any content-producing endpoint

> **Now: fixed.** Listings, messages, reports and photo uploads are
> rate-limited per account (`backend/app/content_limits.py:25-40`, called at
> `backend/app/listings.py:370`, `backend/app/messages.py:116`,
> `backend/app/reports.py:154` and `backend/app/uploads.py:508`), and
> registration and code requests per IP (`backend/app/auth.py:640-645`,
> `:705`). The counters live in process memory, and the IP limits rely on
> `TRUST_PROXY_HEADERS=1` (section 4.5).

**Where:** rate limiting exists only at `backend/app/auth.py:49` and is applied
only to the four auth endpoints. Unprotected:
`backend/app/listings.py:290` (create listing),
`backend/app/messages.py:101` (send message),
`backend/app/uploads.py:41` (upload),
`backend/app/reports.py:106` (create report).

Reproduced: 80 sequential `POST /api/listings` with one token → 80 × 201, no
throttling. Registration with unique addresses → all 201, because the bucket key
includes the email (`backend/app/auth.py:51`).

**Impact:** one account writes unlimited listings, messages and uploads; with H1
and H2 this fills disk and database. Separately, bulk fake-account creation is
not impeded at all.

**Fix:** apply the existing `_rate_limit` bucket keyed on `user.id` to uploads,
listings, messages and reports; add an IP-keyed limit to registration. Note that
a multi-process deployment needs shared state (Redis) — the current bucket is
per-process.
**Effort:** medium (half a day) extending existing infrastructure.

#### H4 — The report endpoint is an existence oracle, and lets an attacker inject private messages into the moderation queue

> **Now: fixed.** `create_report` answers 404 unless the reporter can see the
> target (`_reportable`, `backend/app/reports.py:76-110`, called at `:156`),
> and an account can file 10 reports an hour (`:154`). The id of an active user
> or listing still gets 201 where a missing one gets 404, but those ids are
> visible in the app anyway.

*(Originally rated HIGH by the scanning pass; downgraded to MEDIUM after
verification — reasoning below.)*

**Where:** `backend/app/reports.py:115-117` — the target is fetched by id with no
access check; `backend/app/admin.py:375-388` — `_message_summary` decrypts the
content for the admin view. No rate limit on the endpoint.

Reproduced with account X, which is **not** a participant in match 1:

```
GET  /api/matches/1/messages         (X)   -> 403 "not a participant"
POST /api/reports {message, id=1}    (X)   -> 201
POST /api/reports {message, id=2}    (X)   -> 201
POST /api/reports {message, id=3..11}(X)   -> 404      <- id enumeration oracle
Admin GET /api/admin/reports?target_type=message:
  report#1 message#1 sender=Deniz  PLAINTEXT: "...my address is Nişantaşı..., phone 0532..."
  report#2 message#2 sender=Elif   PLAINTEXT: "IBAN for the deposit: TR33 ..."
```

**Impact, reassessed.** Two real effects: (a) the 201/404 difference enumerates
valid message, user and listing ids with no rate limit; (b) an attacker can push
a private message they are not party to into the moderation queue, breaking
principle 3 ("the admin sees only what the decision requires") from the outside.

**But** the framing "the attacker can read all messages in plaintext" is wrong.
Only the **admin** sees the plaintext. The attacker obtains no content — verified
directly: X could not read a single message. Real privacy damage is therefore
lower than first claimed. → **MEDIUM**.

**Fix:** add an access check in `create_report` — for a message target the
reporter must be a participant in the match, otherwise 404; for a listing, the
listing must be visible to them. Add a per-user rate limit on the endpoint.
**Effort:** low-to-medium.

#### H5 — The `.edu.tr` requirement is client-side only

> **Now: fixed.** Registration accepts only a university address, checked on
> the server (`StudentEmailIn`, `backend/app/auth.py:431-460`; test at
> `backend/tests/test_auth.py:385`). Addresses in `ADMIN_EMAILS` are exempt;
> section 4.1 has the details. The product copy that promises a `.edu.tr`
> sign-up now matches the server.

**Where:** `backend/app/auth.py:159-168` (`EmailIn._normalize` checks only for
`@` and a dot in the domain). The only real check is
`frontend/src/pages/Onboarding.tsx:124`.

Reproduced: `register {"email": "attacker@gmail.com"}` → 201, `verify-otp` → 200,
fully functional account. That account was then used to execute H2, H3 and H4.

**Impact:** the platform's entire trust model — "verified Istanbul university
students" — is not enforced anywhere on the server. This is not just a technical
gap; the product *sells* it. `frontend/src/i18n/translations.ts:659` and `:1531`
say sign-up is only possible with a `.edu.tr` address, and the same claim appears
at `:65`, `:80`, `:88`, `:212`, `:597`, `:605`. Worse, the Safety page carries an
explicit in-code promise that it lists only guarantees *actually implemented*
(`frontend/src/pages/Safety.tsx:14`) — for this card, that promise is false.

Severity is HIGH for the product trust model; direct technical exploitability is
closer to MEDIUM.

**Fix:** add a domain rule to `EmailIn` (`domain == "edu.tr" or
domain.endswith(".edu.tr")`) with an explicit exemption list for the non-`.edu.tr`
address in `ADMIN_EMAILS` (then a hard-coded default in
`backend/app/config.py`, now environment-only), and align it with
`backend/app/universities.py`. If
the rule is *not* going to be enforced, the Safety and landing copy must be
corrected instead.
**Effort:** low.

#### H6 — Account deletion does not delete uploaded photos, and photo URLs are unauthenticated and permanent

> **Now: partly fixed.** Deleting an account deletes the photo files its
> profile and listings point at (`purge_user`, `backend/app/auth.py:1017-1019`,
> `:1101`), and an admin listing deletion deletes the listing's files
> (`purge_listing`, `backend/app/listings.py:210-214`). Both go through
> `delete_unused_photos` (`backend/app/uploads.py:435-472`), which keeps any
> file that a remaining listing or profile still uses. Until 10 October 2026
> only `purge_listing` made that check: account B could copy account A's photo
> URL into its own profile, delete itself, and A's photo answered 404 from then
> on. Tests cover both a profile and a listing still using the file
> (`backend/tests/test_uploads.py:167-214`).
>
> Since 12 October 2026 the two remaining gaps are closed. A photo removed
> from a listing or profile by editing is deleted when the edit commits
> (`backend/app/listings.py:585`, `backend/app/auth.py:888`), through the same
> `delete_unused_photos`. A photo uploaded and never attached is deleted by a
> background sweep once it is older than 7 days (`sweep_orphan_photos`,
> `backend/app/uploads.py:562`; started at boot by `start_orphan_sweeper`,
> `:610`, then daily). "In use" now also counts an unanswered like on a
> photo (`swipes.target_ref`, `photo_names_in_use`, `:440`), because the
> Likes screen shows the liked photo until the owner answers. The sweep refuses to run against a bucket
> when `DATABASE_URL` is unset, and deletes nothing when no record uses any
> photo, so a misconfigured deploy cannot read every file as unused. Tests:
> `backend/tests/test_uploads.py:243-390` and `:610-658`.

**Where:** `backend/app/auth.py:503` (`purge_user` touches only database rows),
`backend/app/listings.py:136` (`purge_listing`, same), `backend/app/main.py:158`
(`StaticFiles` mount with no auth). Confirmed by grep: neither purge function
references `UPLOADS_DIR` or `unlink`.

Reproduced:

```
POST   /api/uploads                     -> /uploads/b58976c0….png
GET    /uploads/b58976c0….png (no auth) -> 200
DELETE /api/auth/me (with password)     -> 204
GET    /uploads/b58976c0….png (AFTER)   -> 200      <- still served
```

**Impact:** students' face and profile photos remain publicly reachable after
they delete their account. This contradicts the product's own promise that
account deletion is permanent and "your profile, listings, matches and messages
are completely deleted" (`frontend/src/i18n/translations.ts:673-674`), and it is an
incomplete response to a KVKK Art. 7 erasure request.

Severity is HIGH on privacy/compliance grounds; technically MEDIUM (the
filenames are 16 random bytes, so an attacker must already know the URL).

**Fix:** in `purge_user` and `purge_listing`, unlink files under `UPLOADS_DIR`
whose names match the `secrets.token_hex(16).<ext>` pattern referenced by the
deleted rows' `photos` arrays. Add simple reference counting for the case where
the same photo is used by more than one row.
**Effort:** low-to-medium (deletion plus the sharing edge case).

### MEDIUM

#### M1 — Login/OTP lockout DoS: five requests lock a victim out of their own account for 15 minutes

> **Now: partly fixed.** Login keys its counter on email plus IP and clears it
> on success (`backend/app/auth.py:752`, `:770`), so an attacker fills only
> their own IP's bucket. **Left:** `request-otp` and `verify-otp` still key on
> the email alone (`:702`, `:788`), so five calls from anyone block that
> address's code sign-in for 15 minutes. For `verify-otp` that is deliberate
> (section 4.5), and password login stays open.

*(Rated HIGH by the scanning pass; downgraded — availability-only, reversible, no
confidentiality or integrity loss.)*

**Where:** `backend/app/auth.py:49-58` — the bucket key is `(action, email)` with
no IP dimension, and a successful login does not clear the bucket. Called at
`backend/app/auth.py:361`.

Reproduced: 5 wrong passwords from the attacker → 401 ×5; then the **victim**
with the correct password → 429 "too many attempts… 15 minutes".
`request-otp` and `verify-otp` behave the same.

**Impact:** anyone who knows a victim's email address can keep them locked out in
15-minute increments.

**Fix:** add an IP dimension to the key; **reset the bucket on successful
login**; prefer exponential backoff over an email-keyed hard lockout.
**Effort:** low-to-medium.

#### M2 — `password_hash` and `otp_hash` appear in plaintext in error logs; `otp_hash` inverts in ~0.3 s

> **Now: fixed.** The engine is created with `hide_parameters=True`
> (`backend/app/db.py:78`), and codes are stored as HMAC-SHA256 under
> `OTP_KEY` (`backend/app/auth.py:314-319`), which `render.yaml` generates.
> Without `OTP_KEY` storage falls back to plain SHA-256 with a warning — now
> only locally; in production (`DATABASE_URL` set) the app refuses to start
> instead (`backend/app/startup_checks.py`, section 4.2).

**Where:** `backend/app/db.py:44` — `create_engine(...)` is called without
`hide_parameters=True`.

Reproduced against the real engine with a failing INSERT:

```
hide_parameters: NOT set (parameters visible)
password_hash visible in exception: True
otp_hash      visible in exception: True
[parameters: ('deniz@…', 'SALT$SECRETDIGEST…', 'c658c2f6…OTPHASH')]
```

`otp_hash` is an unsalted SHA-256 over a 6-digit code — a 10⁶ search space,
seconds on any CPU. Anyone with access to Render's logs (or who catches a 500
window) can recover a live OTP.

**Impact:** conditional (requires a 500 *and* log access), but the consequence is
account takeover. The `password_hash` exposure is much less serious because it is
scrypt-protected; the sharp edge is the OTP.

**Fix:** `create_engine(..., hide_parameters=True)`; store the OTP as
`HMAC-SHA256(server_secret, code)` instead of a bare hash.
**Effort:** very low for the one-liner; slightly more for the HMAC change.

#### M3 — Email enumeration (explicit, plus a timing channel)

> **Now: partly fixed.** `request-otp` gives the same 200 and text for
> registered and unregistered addresses (`backend/app/auth.py:707-709`), and
> registration is limited to 10 an hour per IP (`:640-645`). **Left:**
> `register` still answers 409 for a taken address, on purpose (`:649-664`);
> `request-otp` answers 403 for a suspended account (`:712`), and it is slower
> for a registered address because only then does it send an email through
> Brevo; login still skips the scrypt work for an unknown address
> (`:754-759`).

**Where:** `backend/app/auth.py:317-319` (register returns 409 "already
registered"), `backend/app/auth.py:338-341` (request-otp returns 404 "not
registered"), and `backend/app/auth.py:363-368` — when the user does not exist,
`_verify_password` is never called, so no scrypt work is done and the response is
measurably faster.

Reproduced:

```
register   {registered address}    -> 409 "already registered"
request-otp{unregistered address}  -> 404 "not registered"
request-otp{registered address}    -> 200
12 DIFFERENT @marmara.edu.tr       -> [404] × 12, no 429 at any point
```

The last line is the important one: the rate limiter is keyed on the email, so
scanning *different* addresses is unlimited.

**Impact:** "is X on this platform" is answered to strangers, and Turkish
universities use predictable `firstname.lastname@ogr.university.edu.tr` patterns,
so a student roster can be scanned. Sensitive on a roommate platform.

**Fix:** return a uniform 200 from `request-otp`; for register, either send an
"you already have an account" email and return 200, or accept the leak
consciously; add an IP-keyed limit; run a dummy scrypt verification when the user
does not exist to flatten the timing channel.
**Effort:** low-to-medium — doing this without breaking the registration UX takes
some thought.

#### M4 — Upload URLs are derived from the `Host` header, and static files carry no `nosniff` / `Content-Disposition`

> **Now: fixed.** Upload URLs are built from `PUBLIC_BASE_URL` when it
> is set (`public_base_url`, `backend/app/uploads.py:136-145`), and
> `render.yaml` sets it to `https://api.evdes.tr`. Files under `/uploads/`
> carry `nosniff`, `Content-Disposition: attachment` and
> `Cross-Origin-Resource-Policy` (`backend/app/main.py:184-199`, `:222-223`).
> Listing and profile photos must pass the same allowlist
> (`is_allowed_photo_url`, `backend/app/uploads.py:343-377`): the app's own
> `/uploads/` files, plus `https` hosts listed in `EXTRA_PHOTO_HOSTS`. For
> profiles the check is `_check_profile_photos`
> (`backend/app/auth.py:835-861`, called at `:871-872`), which lets a URL
> already on the profile stay, so a profile saved before the check can still
> be edited; it can drop that URL but not add another like it. A deployment
> without `PUBLIC_BASE_URL` still takes the URL from the `Host` header.

**Where:** `backend/app/uploads.py:75` builds the returned URL from
`request.base_url`; `backend/Dockerfile:43` runs uvicorn with
`--forwarded-allow-ips '*'`; `backend/app/main.py:158` mounts `StaticFiles` with
no header customisation.

Reproduced:

```
POST /api/uploads -H "Host: evil.attacker.tld"
  -> {"url": "http://evil.attacker.tld/uploads/….png"}
GET /uploads/<file> response headers: content-type: image/png
  (no X-Content-Type-Options, no Content-Disposition)
```

**Impact:** the poisoned URL can be written into a `photos[]` array and is then
served to other users inside an `<img src>`, leaking their IP and User-Agent to
the attacker's server (tracking), and allowing post-moderation content swaps.
Whether Render forwards a client-controlled `Host` in production could not be
verified (attacking production is out of scope). This is *not* an XSS today —
separate origin, and the browser does not sniff.

**Fix:** build the URL from a fixed `PUBLIC_BASE_URL` / `UPLOADS_BASE_URL`
environment variable; restrict `photos` elements to an allowlist of the app's own
`/uploads/` prefix (which closes the URL half of H2 at the same time); add
middleware that sets `X-Content-Type-Options: nosniff` and
`Content-Disposition: attachment` on static responses.
**Effort:** low.

#### M5 — No security headers on either the API or the frontend

> **Now: fixed.** The API adds `X-Content-Type-Options`, `Referrer-Policy`,
> `X-Frame-Options`, `Permissions-Policy`, a strict `Content-Security-Policy`
> (`default-src 'none'; frame-ancestors 'none'; base-uri 'none'`, skipped only
> on the `API_DOCS` pages so Swagger still loads) and, over HTTPS, HSTS to every
> response (`SecurityHeadersMiddleware` in `backend/app/main.py`; tests in
> `backend/tests/test_security_headers.py`). `frontend/vercel.json:74-104`
> gives the site its own CSP and the same set of headers. Not checked against
> production (section 11).

**Where:** `backend/app/main.py:161-187` — the only middleware is GZip and CORS;
no security-header middleware exists. `frontend/vercel.json` contains a SPA
rewrite and nothing else — no `headers` block.

Verified by reading the code and `vercel.json`; production response headers were
deliberately **not** fetched (see section 11).

**Impact:** the session token lives in `localStorage`
(`frontend/src/lib/api.ts:16-20`), so any future XSS converts directly into
session theft; no CSP and no `frame-ancestors` means no clickjacking defence; no
HSTS on the API.

**Fix:** a small FastAPI middleware emitting `X-Content-Type-Options: nosniff`,
`Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` and HSTS; a `headers`
block in `frontend/vercel.json` adding CSP, XCTO and XFO.
**Effort:** low.

### LOW

#### L1 — The suspension reason (a free-text admin note) is shown to the suspended user, and can expose the reporter

> **Now: open.** Login still returns the reason
> (`backend/app/auth.py:766`). Until that changes, runbook A's rule applies:
> never name a reporter in the reason.

**Where:** `backend/app/auth.py:375` calls
`_reject_if_suspended(user, include_reason=True)` on the login path;
`SuspendIn.reason` (`backend/app/admin.py:133`) is unfiltered free text.

Reproduced:

```
suspend reason = "…reported by Cem"
login (correct password) -> 403 "…Reason: …reported by Cem"   <- leaks
request-otp              -> 403 generic sentence              <- does not leak
```

The current design is already a deliberate improvement — the docstring at
`backend/app/auth.py:67-101` explains that the reason used to be returned
unconditionally, so a stranger who only knew the email address could read the
full moderation note via `request-otp`. Now it is shown only after the password
is verified.

**Impact:** the person who proves the password *is* the person who was reported,
which conflicts with admin principle 2 ("the reporter is never shown to the
reported"). Mitigated by the fact that the note is admin-written, so an admin can
simply choose not to name anyone. → LOW-to-MEDIUM.

**Fix:** a separate `internal_note` column plus a user-facing reason *code*; or,
cheaper, a warning in the admin UI that this text will be shown to the user.
**Effort:** medium (schema plus UI).

#### L2 — `_RATE_BUCKETS` grows without bound (slow memory leak)

> **Now: fixed.** Buckets idle for longer than the longest window are dropped,
> at most once a minute, and the table is capped at 10,000 keys, oldest first
> (`backend/app/auth.py:87-113`). Under a flood of fresh keys the cap can
> evict an old bucket early.

**Where:** `backend/app/auth.py:46` and `:51` — `setdefault` creates a key that is
never removed; the pruning at `:52` only trims the timestamp list inside a bucket
that is being accessed.

Every unique email address ever seen leaves a permanent dictionary key. A
measurement of 200k unique addresses reported ~59.5 MiB; the mechanism is
confirmed by reading the code. This should be addressed as part of fixing H3.

**Fix:** a TTL-bounded LRU (`cachetools.TTLCache`) or periodic sweep; Redis for
multi-process deployments.
**Effort:** low.

#### L3 — Anonymous `GET /api/listings` returns the owner's name and university

> **Now: fixed.** Anonymous callers get listings without `owner_name` and
> `owner_university` (`_hide_owner`, `backend/app/listings.py:345-358`).
> `owner_id` stays, on purpose.

**Where:** `backend/app/listings.py:285-286` (`owner_name`, `owner_university` on
`ListingOut`) with the endpoint depending on `get_optional_user`
(`backend/app/listings.py:325`).

Reproduced:

```
anon GET /api/listings ->
  {'owner_id': 1, 'owner_name': 'Deniz', 'owner_university': 'Yıldız Teknik Üniversitesi'}
```

**Impact:** a scraper with no account collects name + university + district +
photos, and `owner_id` hands it ready-made ids for the H4 oracle.

**Fix:** return `owner_name` / `owner_university` only to authenticated callers
(None for anonymous), or move the endpoint to `get_current_user`.
**Effort:** low.

#### L4 — Match/like enumeration via the 404-vs-403 distinction

> **Now: fixed.** Non-participants get 404, the same answer as a missing id
> (`backend/app/messages.py:50-63`, `backend/app/swipes.py:260-264`).

**Where:** `backend/app/messages.py:53-57` (non-participant → 403) and
`backend/app/swipes.py:261` (respond → 403). No content leaks; only the existence
and rough count of rows is observable.

Worth noting for consistency: `backend/app/swipes.py:263` deliberately returns
**404** for a suspended swiper (so suspension status does not leak) but leaves
**403** for a non-participant — the same reasoning was applied to one branch and
not the other.

**Fix:** return 404 to non-participants as well.
**Effort:** very low.

#### L5 — No entropy check on the raw-string `MESSAGE_KEY` path

> **Now: open.** Unchanged (`backend/app/crypto.py:111-112`).

**Where:** `backend/app/crypto.py:111-112` — only a length check (≥ 32) followed
by a single unsalted SHA-256.

Verified by code reading. Production risk is small because `render.yaml` uses
`generateValue: true`, which yields a high-entropy string; the exposure is an
operator who pastes a weak value by hand. If a database dump leaks, a weak key is
then dictionary-attackable.

**Fix:** accept only `base64(32 bytes)` and fail loudly at startup on a malformed
value rather than silently falling back to plaintext; or apply scrypt/argon2 plus
an entropy threshold on the raw path.
**Effort:** low.

#### L6 — Other hardening items

> **Now:** six of the nine items are fixed; the last column has each one.

| Item | Where | Found | Fix | Now |
|---|---|---|---|---|
| `/docs` and `/openapi.json` open in production | `backend/app/main.py:147` (no `docs_url=None`) | 200/200 locally; not directly exploitable since authz is enforced, but it eases reconnaissance | `docs_url=None, redoc_url=None, openapi_url=None` in production | **Fixed.** Off unless `API_DOCS=1` (`backend/app/config.py:128`, `backend/app/main.py:365-371`); all three paths answer 404 (`backend/tests/test_api_docs.py`) |
| `DEV_OTP` code default is `"1"` | `backend/app/auth.py:136` | `render.yaml` pins `"0"`, so *this repo's* production is safe; risk is any deployment not using the blueprint. Reproduced locally: the first account to register an `ADMIN_EMAILS` address became admin instantly, and the OTP came back in the response body | Default to `"0"` so the unsafe value is opt-in | **Fixed.** Default `"0"` (`_dev_otp_enabled`, `backend/app/auth.py:344-352`); with the variable unset, no code comes back in the response (`backend/tests/test_auth.py:176`). `render.yaml` still pins `"0"` |
| scrypt N=2¹⁴ | `backend/app/auth.py:40` | Below OWASP's N=2¹⁷; `password_hash` is `String(200)`, which accommodates an upgrade | Raise N, re-hash on next successful login | **Open.** `backend/app/auth.py:47` |
| AES-GCM used without AAD | `backend/app/crypto.py:153`, `:175` | Ciphertext is not bound to its row, so a DB-write attacker could move messages between rows. Requires database write access — this is defence-in-depth, not a primary control | Pass `message.id` / `match_id` as associated data | **Open.** |
| Container runs as root | `backend/Dockerfile` (no `USER` directive) | — | Add a non-root `USER` | **Fixed.** The server runs as an unprivileged `app` user (`backend/Dockerfile:41-51`). Code and the trained model stay owned by root, so it can read them but not change them; only `data/` is writable. Checked by running the API as that user with the image's file layout; no image was built here |
| No KVKK privacy notice; Brevo/Render transfers undisclosed | no `/privacy` route exists | Anthropic *is* disclosed honestly (`translations.ts:1534`); Brevo and Render appear nowhere | Write the notice, add the route | **Fixed.** `/privacy` exists and names Render, Neon, Cloudflare R2, Vercel, Brevo, Google Fonts and OpenStreetMap, and says what the audit trail keeps (section 8.4) |
| `react-router-dom@6.30.1` | `frontend/package.json` | `@remix-run/router` open-redirect XSS advisory (fixed in 6.30.4+). **No concrete path from untrusted input to navigation was found in this codebase** — vulnerable version only, exploitability not demonstrated | `npm audit fix` | **Fixed.** `frontend/package-lock.json` resolves 6.30.6, the last 6.x release. Two newer advisories are fixed only in 7.18: an open redirect through a backslash in a `<Link>` or `navigate()` path (GHSA-wrjc-x8rr-h8h6), and one in server-side rendering, which this app does not do (GHSA-337j-9hxr-rhxg). Every navigation target in `frontend/src` is a constant, `-1` or `/chat/<numeric id>`, so no user input reaches the first. React Router 7 closes both |
| Python dependencies pinned with `>=` | `backend/requirements.txt` | Non-reproducible builds; no known critical CVE in the currently installed versions | Pin exact versions, add a lockfile | **Fixed.** `backend/requirements.txt` is now a lock generated from `backend/requirements.in`: every package, dependencies of dependencies included, at an exact version. `pytest` and `httpx` are pinned in `requirements-test.txt`. `pip-audit` found no known vulnerability in the pinned versions on 10 October 2026. Nothing refreshes the lock on its own; `requirements.in` has the command |
| Deleted account's email survives in the audit trail | `backend/app/admin.py:1416-1422` (`detail`), `backend/app/admin.py:1202-1225` (search-prefix narrowing can reconstruct an email letter by letter) | Only relevant against a curious-admin model | Store a hash or a redacted form; drop email search | **Open, disclosed.** The privacy notice lists what the record keeps (section 8.4) |

---

## 11. Not verified, corrected, or overstated

Recording these matters as much as recording the findings.

- **"An attacker can read ALL private messages in plaintext via the report
  oracle."** Partly false. Only the **admin** sees plaintext. Verified directly:
  the attacking account was never a participant in the match and could not read a
  single message — it could only push the message into the queue. H4 was
  downgraded to MEDIUM accordingly.
- **Login lockout / OTP oracle rated "HIGH".** Availability-only and fully
  reversible → MEDIUM.
- **Production `DEV_OTP=0`, production `Host` header behaviour, production
  security headers.** Attacking production is out of scope, so these are
  confirmed only from code and from `render.yaml` plus a local instance. The
  claim that production returned no HSTS/CSP/XCTO/XFO came from a `curl -I`
  observation reported during the audit and was **not independently re-verified
  here**. The code now sends those headers (M5); nobody has checked
  production's responses since.
- **`react-router-dom` advisory.** The audit found no exploitable path within
  this application. The version it flagged is gone (6.30.6 now); the two newer
  advisories that remain have no path here either (L6).

---

## 12. Areas that were attacked and held

These were probed and did not break. They are listed so that a future reader
does not re-litigate them, and so that a future change that breaks one of them is
visibly a regression.

- **IDOR.** Attacker → `PATCH`/`DELETE` on another user's listing → 403
  (`backend/app/listings.py:530`, `:591`). `POST` to a match they are not part of
  → 404 since the L4 fix (`backend/app/messages.py:60-62`). `GET` of an
  inactive listing → 404.
- **Mass assignment.** `PATCH /api/auth/me` with `is_admin`, `verified`, `email`,
  `university`, `password_hash`, `is_suspended`, `id` → none changed. The schema
  does not declare them (`backend/app/auth.py:528`) and `is_admin` is a property,
  not a column (`backend/app/models.py:83`).
- **Admin authorization.** Non-admin → `GET /api/admin/summary` → 403; anonymous
  → 401 (`backend/app/reports.py:54`).
- **SQL injection.** `/api/admin/users?q=` with `'`, `' OR 1=1--`,
  `a%' UNION SELECT 1,2,3--`, `%`, `_` → all 200, no errors. Raw SQL exists only
  in `backend/app/migrate.py` and interpolates a constant schema; user input never
  reaches it.
- **File-type and path traversal on upload.** Magic-byte signature verification
  (`backend/app/uploads.py:112-120`) rejects SVG/HTML with 415; the stored filename
  is generated server-side (`backend/app/uploads.py:510`) so `../` in the client
  filename is irrelevant.
- **Session hygiene.** Suspension and password change drop all tokens
  (`backend/app/admin.py:1336`, `backend/app/auth.py:906`); 30-day TTL enforced
  on read; `get_optional_user` re-checks suspension as a second gate
  (`backend/app/auth.py:616`).
- **Foreign-key cleanup on account deletion.** A user with heavy FK references
  deleted cleanly (204, no 500). The nullable-FK sweep is derived from SQLAlchemy
  metadata rather than a hand-maintained list
  (`backend/app/auth.py:912-938`) — the docstring records that the same
  "cannot delete account" bug recurred three times before this. *(Photo files
  are deleted too now, except ones another account still uses; see H6.)*
- **CORS.** `allow_credentials` is never passed, so it defaults to False
  (`backend/app/main.py:421-429`); no ACAO is returned to an arbitrary origin.
- **SSRF.** No user-supplied URL is ever fetched by the server; photo URLs are
  stored and echoed, never dereferenced server-side.
- **Frontend XSS.** No `dangerouslySetInnerHTML`, `innerHTML`, `eval`, or
  user-controlled `href`; React escapes by default. Photo URLs only ever land
  in `<img src>`, and new listing and profile photos must pass the photo
  allowlist, which turns away `javascript:` and `data:` URLs (M4).
- **OTP cryptography.** CSPRNG generation, single use, 5-attempts-per-15-minutes,
  10-minute TTL, constant-time comparison (`backend/app/auth.py:337-341`,
  `:322-334`). *(The storage weakness, M2, is fixed: codes are stored under an
  HMAC key.)*

---

## 13. Known gaps and accepted risks

Things this platform deliberately does not do, or does not yet do. None of these
are findings; they are the boundaries of the current design.

1. **Identity is an email address.** No student-card verification, no phone
   number, no ID check. A determined bad actor re-registers after a ban. Since
   the H5 fix the new address must at least be a university one (section 4.1).
2. **Admin authority is a string comparison.** No role table, no separation
   between "can suspend" and "can permanently delete". Admin sign-in does take
   two factors (the password and a code sent to the admin's inbox), but the
   second factor is still email; an authenticator app (TOTP) would be the next
   step. There is also no password reset: an admin who forgets the password
   cannot sign in as admin (the code tab asks for it too), so keeping a second
   admin address with its own password is the practical backup. Documented at
   `backend/app/config.py`.
3. **Encryption is at-rest only.** The server can and does read messages —
   necessarily, because moderation runs on plaintext. See section 7.2.
4. **No key rotation.** Losing `MESSAGE_KEY` permanently destroys all encrypted
   messages. The only recovery is an operator's manual backup of the value.
5. **Rate limiting is per-process and in-memory.** It resets on restart and does
   not work correctly under more than one worker. The IP limits also depend on
   `TRUST_PROXY_HEADERS=1` and on Render being the only proxy in front of the
   app (section 4.5).
6. **Uploads are public, and durable only with a bucket.** With `S3_BUCKET`
   set, photos live in R2 and survive redeploys; without it they fall back to
   the container disk, which the Render free plan wipes (`DEPLOY.md` §1.5).
   Files are served to anyone with the URL (`serve_photo`,
   `backend/app/uploads.py:524-527`). Account deletion and admin listing
   deletion remove the files from whichever store is in use, unless another
   listing or profile still uses them; a user's own listing "delete" is a
   deactivation and keeps them (item 7). Photos removed by editing are
   deleted when the edit is saved; photos uploaded and never attached are
   deleted by a daily sweep once they are a week old (H6).
7. **Listing deletion is deactivation, not deletion.** `DELETE
   /api/listings/{id}` sets `is_active=False` and the row stays
   (`backend/app/listings.py:592`). The Safety copy says this explicitly
   (`frontend/src/i18n/translations.ts:677-678`). Only *account* deletion is
   permanent.
8. **A user cannot re-publish their own deactivated listing.** Republishing
   currently goes through an admin (`POST /api/admin/listings/{id}/publish`).
   Documented honestly in the endpoint docstring at
   `backend/app/listings.py:568-585`.
9. **No user-level block or mute.** The only remedies are report and admin
   suspension.
10. **Visitors' IP addresses reach Google and OpenStreetMap.** Fonts load
    from Google Fonts and map tiles from OpenStreetMap. The privacy notice
    discloses both (section 8.4); self-hosting the fonts would remove one.
11. **Moderation is intentionally lenient.** `block` is reserved for
    unambiguous violations; fraud heuristics can never block on their own
    (`backend/app/moderation.py:70-72`). Since October 2026 the two strong
    scam combinations (`moderation.HOLD_FOR_REVIEW`: IBAN with urgency, money
    or deposit; a deposit before viewing) hold a listing out of the deck
    until an admin approves it (`Listing.pending_review`). Weaker scam
    signals, and every scam signal in chat, still only flag, so scam
    listings phrased another way *will* get published and depend on user
    reports.

---

## 14. Incident response runbook

What is actually possible today, with the endpoint that does it. Anything not
listed here does not exist.

### A. A user is scamming, harassing, or spamming

1. **Suspend the account** — `POST /api/admin/users/{id}/suspend` with a reason
   (`backend/app/admin.py:1311`). This immediately: blocks login, **deletes all
   of their sessions** (`:1336-1338`), and hides their listings. It does *not*
   touch `is_active`, so unsuspending restores everything exactly
   (`backend/app/admin.py:1346`).
2. **Mind what you write in the reason.** It is shown to the user on their next
   login attempt (finding **L1**). Never name a reporter.
3. Reversible. Prefer this over deletion, always.

### B. Content must come down

- **Listing:** `POST /api/admin/flagged/listing/{id}/review` to remove.
  Reversible via `POST /api/admin/listing/{id}/restore`; the removed item stays
  findable at `GET /api/admin/flagged?status=removed`.
- **Message:** same review endpoint. The text is moved to `original_content` and
  replaced by the `[removed_by_moderation]` sentinel; the row is kept so the
  conversation's ordering and context are not destroyed
  (`backend/app/admin.py:88-92`). Reversible — *except* for messages removed
  before those columns existed, where the text is genuinely gone and restore
  returns `restored:false`.

### C. Data must be permanently erased (legal request, real-person data)

- `DELETE /api/admin/users/{id}` or `DELETE /api/admin/listings/{id}`, both with
  a **mandatory reason**, both writing an `AdminAction`
  (`backend/app/admin.py:1382`, `:1144`).
- **Conversations survive a listing deletion by design** —
  `matches.listing_id` is NULLed (`backend/app/listings.py:206-208`).
- **Photo files go with the rows.** Both endpoints delete the files the
  deleted rows pointed at, from R2 or the container disk (`purge_user`,
  `backend/app/auth.py:1101`; `purge_listing`,
  `backend/app/listings.py:210-214`), and the response's `cleanup.photos`
  says how many. A file that another listing or profile still uses stays.
- Photos the person removed by editing are already gone. Photos they
  uploaded and never attached stay until the sweep deletes them, at most
  about 8 days after upload (H6).
- ⚠️ The audit entry keeps the deleted account's email, name and university
  (`backend/app/admin.py:1416-1422`). The privacy notice says so (section 8.4).

### D. A session is believed to be compromised

- **The user's own move:** `POST /api/auth/change-password` — this deletes every
  token for that user (`backend/app/auth.py:906-908`), a genuine
  log-out-everywhere.
- **The admin's move:** suspend, which drops all tokens
  (`backend/app/admin.py:1336`), then unsuspend. Clumsy, but it is the only
  admin-side session revocation that exists.
- **There is no "revoke all tokens" endpoint** and no per-device session list.
- Worst case: delete every row in `auth_tokens` directly in the database. Every
  user is logged out.

### E. `MESSAGE_KEY` is believed to be compromised

**Rotation is not supported.** Changing the key makes every existing encrypted
message permanently unreadable — they will render as `[unreadable]`
(`backend/app/crypto.py:51`, `:176-179`). There is no re-encryption script.

Doing it anyway requires writing a migration that decrypts with the old key and
re-encrypts with the new one, run while both keys are available. Plan for this
before you need it.

### F. The service is being flooded (H1 / H2 / H3)

The app throttles on its own now: request bodies are capped at 6 MB,
listings, messages, reports and uploads are limited per account, and registration and code requests per IP (section 4.5). The
counters reset when the container restarts. When that is not enough:

1. Rate-limit or body-cap at Render / Cloudflare.
2. Identify the offending account and suspend it (which kills its tokens).
3. If a bloated row is being served to everyone, delete or truncate it
   directly in the database — `GET /api/listings` is anonymous, so every visitor
   pays for it until you do. H2's caps stop new rows from growing that large.

### G. Suspected admin-account compromise

1. Remove the address from `ADMIN_EMAILS` in the Render environment and
   redeploy. Because `is_admin` is computed per request from that set
   (`backend/app/models.py:83`), authority disappears on the next request — no
   database change needed. This is the fastest kill switch in the system.
   **If it is the only address, replace it instead of emptying the variable**
   (for example with `yok@invalid`): an empty list stops a production boot
   (`backend/app/startup_checks.py`), Render then keeps serving the previous
   deploy, and the compromised address would stay admin.
2. **An admin cannot suspend or delete another admin** — this is intentional
   (`backend/app/admin.py:1226`). Step 1 is the mechanism; there is no in-app
   alternative.
3. Review `GET /api/admin/actions` (`backend/app/admin.py:1448`) for
   `user_delete` / `listing_delete` / `listing_update` entries. Note that
   reversible actions such as suspensions are *not* in this table by design —
   look at `suspended_by` / `reviewed_by` / `resolved_by` columns for those.

---

## 15. Limitations of this document

- **Production was never tested.** Every reproduction ran against a local
  instance with an isolated SQLite database. Production runs Postgres behind
  Render's proxy; behaviour that depends on the proxy (M4's `Host` handling,
  M5's response headers, H1's body limits) may differ. Section 11 lists what
  this affects.
- **This is not a full penetration test.** It covers the HTTP API, the
  authentication and authorization model, cryptography and the data model. It
  does *not* cover Render's or Vercel's infrastructure, DNS, the email delivery
  path beyond the API call, business-logic abuse of the matching algorithm, or
  the ML pipeline (`scripts/train_model.py`, model file integrity).
- **Dependency checks are one-off.** `npm audit` and, since the Python
  dependencies were locked, `pip-audit` were run by hand on 10 October 2026.
  Nothing re-runs them: a new advisory against a pinned version shows up only
  when someone runs them again. Apart from React Router (L6), every
  `npm audit` finding on that date was in a build or test tool: Tailwind's
  dependencies, Vite, Vitest and ESLint. Those run on a developer's machine,
  in CI and in the Vercel build, never in the browser. The Vite and Vitest
  ones concern their local servers (`npm run dev`, the Vitest UI) and matter
  only when one is reachable from another machine; several need a major
  upgrade (Vite 6, Vitest 4).
- **Static review only for `frontend/`** apart from the two claims checked
  directly (client-side `.edu.tr` validation, token storage). No browser-side
  dynamic testing was performed.
- **The findings are a snapshot.** The write-ups in section 10 reflect the
  repository at commit `51e5bb4` on branch `main`. Most were fixed in `dfd79b8`,
  the commit that added this document, and in later commits. The table at the
  top of section 10 records where each stood on 10 October 2026, checked
  against the code and its tests, not against production.
- **Section 10 severities are judgement calls.** Two findings were explicitly
  downgraded from an earlier assessment (H4, M1) because verification showed the
  practical impact was smaller than the initial claim. Reasonable people can
  disagree; the reproduction steps are included so you can form your own view.
