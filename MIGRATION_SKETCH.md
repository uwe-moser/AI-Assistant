# ApexFlow — Migration off Gradio

A pragmatic plan to replace the Gradio UI with a stack that:

- hosts the editorial design from `design_proposal.html`,
- can be **deployed for ~free** with Vercel + a small backend host,
- gates the product behind **Clerk** authentication,
- keeps every line of agent logic intact.

---

## 1 · Why migrate

Gradio is excellent for prototypes and Hugging Face demos, but it constrains
the UI in three ways that matter for a customer-facing portfolio piece:

- **Layout primitives are fixed.** Rows, Columns, Accordions and Dataframes
  carry their own DOM and styling. Custom CSS only takes you so far before
  you fight the framework.
- **Typography & motion are limited.** Loading custom fonts, choreographing
  entrance animations, building a true asymmetric grid — all hostile.
- **Auth and multi-user are afterthoughts.** Adding Clerk to Gradio is
  possible but ugly; in Next.js it's three lines.

The migration target should give us full design control, real auth, and a
clean public deployment path — while leaving all the hard-won Python
(LangGraph, Playwright, ChromaDB, scheduler, sandbox) untouched.

---

## 2 · Recommended stack

```
   Browser
      │
      ▼
┌─────────────────────────────┐
│  Vercel (Hobby — free)      │
│  ───────────────────────    │
│  Next.js 15 · App Router    │
│  React 19 · TypeScript      │
│  Tailwind + CSS variables   │
│  Motion · shadcn/ui         │
│  @clerk/nextjs middleware   │ ◄────────────────────┐
└──────────────┬──────────────┘                      │
               │  HTTPS + Clerk JWT                  │  Sign-in / sign-up
               ▼                                     │
┌─────────────────────────────┐         ┌────────────┴──────────┐
│  Backend host (Fly.io       │         │  Clerk (free ≤10k MAU)│
│   ~$3–5/mo · or Hetzner)    │         │  - hosted auth UI     │
│  ───────────────────────    │         │  - JWKS for FastAPI   │
│  FastAPI (uvicorn)          │         │  - org/role support   │
│  - REST: sessions, tasks…   │         └───────────────────────┘
│  - WebSocket: chat stream   │
│  - Verifies Clerk JWT       │
│  - APScheduler in-process   │
│  - Playwright Chromium      │
│  - Docker-in-Docker sandbox │
│  - SQLite on /data volume   │
└─────────────────────────────┘
```

**Why this combination**

- **Vercel for the frontend only.** The marketing page and product UI are
  static-ish React; Vercel's free Hobby tier is purpose-built for this and
  ships with a global CDN.
- **A real VM or container host for the backend.** ApexFlow's backend
  needs things Vercel functions cannot give it (see §3).
- **Clerk** is the lowest-friction managed auth: a `<SignIn />` component, a
  middleware import, and a JWT your FastAPI can verify against Clerk's JWKS.
  Free tier is 10 000 monthly active users — far past portfolio scale.

---

## 3 · Hosting reality (Vercel limits)

Vercel's free tier is great for the frontend and **cannot host the agent
backend**. The constraints are absolute, not configuration issues:

| Vercel function limit          | Why it breaks ApexFlow                              |
|--------------------------------|-----------------------------------------------------|
| 10 s execution (Hobby)         | A single Browser/Research superstep often exceeds it |
| No persistent filesystem       | SQLite checkpoints, ChromaDB and `sandbox/` vanish  |
| No long-running processes      | APScheduler / TaskRunner can't live there           |
| No WebSocket on Hobby          | Streaming the chat needs WS or long-lived SSE       |
| ~250 MB function bundle        | Playwright Chromium alone is ~280 MB                |
| No Docker-in-function          | The Python REPL sandbox can't run                   |

The realistic split:

| Layer                    | Where it lives                          | Cost              |
|--------------------------|-----------------------------------------|-------------------|
| Marketing page + UI      | **Vercel Hobby**                        | free              |
| Auth (sign-in/sign-up)   | **Clerk**                               | free (≤10k MAU)   |
| FastAPI + agents + tools | **Fly.io** machine + 3 GB volume        | ~$3–5/mo          |
| (alt) same backend       | **Hetzner CX22** VM                     | ~€4.59/mo         |
| Vector store             | starts on-disk (Chroma); later Supabase | free → free tier  |
| Object storage (uploads) | starts on-disk; later Cloudflare R2     | free → 10 GB free |

If you can absolutely not pay for a VM, two fallbacks:

1. **Self-host the backend** on a home machine and expose it with a
   **Cloudflare Tunnel** (free) or **Tailscale Funnel** (free). Frontend on
   Vercel still works because it's just a public HTTPS endpoint.
2. **Strip the heavy agents** (Browser, Documents-with-Playwright, sandboxed
   REPL) and run a reduced backend on Fly.io's small free-equivalent
   machine. The Research, Knowledge and Job-Search agents survive.

Cleanest honest stack: **Vercel + Clerk + Fly.io**. Three dashboards, one
domain, ~$5/mo all-in.

---

## 4 · Authentication with Clerk

**Frontend (Next.js):**

```ts
// web/middleware.ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isProtected = createRouteMatcher(["/app(.*)"]);          // /app/* gated
export default clerkMiddleware((auth, req) => {
  if (isProtected(req)) auth().protect();
});
```

```tsx
// web/app/layout.tsx
import { ClerkProvider } from "@clerk/nextjs";
export default function RootLayout({ children }) {
  return <ClerkProvider>{children}</ClerkProvider>;
}
```

The marketing page at `/` stays public (good for SEO and the customer pitch).
Everything under `/app/*` requires sign-in. The `<UserButton />` drops into
the top nav.

**Backend (FastAPI) — verify the Clerk JWT:**

```python
# api/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt
import httpx, functools

JWKS_URL = "https://<your-clerk-frontend-api>/.well-known/jwks.json"

@functools.lru_cache
def jwks() -> dict:
    return httpx.get(JWKS_URL, timeout=5).json()

def current_user(token = Depends(HTTPBearer())) -> str:
    try:
        claims = jwt.decode(
            token.credentials, jwks(),
            algorithms=["RS256"], options={"verify_aud": False},
        )
        return claims["sub"]            # Clerk user_id
    except Exception:
        raise HTTPException(401, "Invalid Clerk token")
```

Every protected route takes `user_id: str = Depends(current_user)` and
scopes its query by it. The frontend attaches the token automatically:

```ts
const { getToken } = useAuth();
fetch("/api/sessions", { headers: { Authorization: `Bearer ${await getToken()}` } });
```

For WebSockets (chat), pass the token as a query param and call
`current_user` inside the handler — Clerk tokens are short-lived, so
re-issue on reconnect.

---

## 5 · Multi-tenancy (the real schema change)

Today every SQLite table is implicitly single-user. The migration adds a
`user_id` column to every user-owned row and an index on it:

```sql
ALTER TABLE sessions ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local';
CREATE INDEX idx_sessions_user ON sessions(user_id);
-- repeat for: scheduled_tasks, jobs, interviews, knowledge_documents
```

`SessionManager`, `_list_tasks`, `jobs.list_jobs`, `interview.list_sessions`
each grow a `user_id` argument. The default `'local'` keeps the migration
backwards-compatible for your existing local data.

For ChromaDB, scope by metadata filter: every chunk gets
`metadata={"user_id": user_id}` and queries pass `where={"user_id": user_id}`.

The `sandbox/` directory becomes `sandbox/<user_id>/` so file ops can't
cross tenants. This is the one place I'd add a hard isolation check, since
the Python REPL agent runs real code.

When you outgrow SQLite (somewhere around dozens of concurrent users),
swap to **Neon** or **Supabase Postgres** — both have generous free tiers
and pgvector for the knowledge base. The data model doesn't change.

---

## 6 · What stays vs. what changes

| Layer                          | Today (Gradio)                | After migration                   |
|--------------------------------|-------------------------------|-----------------------------------|
| Orchestrator (`sidekick.py`)   | unchanged                     | **unchanged**                     |
| Specialist agents (`agents/`)  | unchanged                     | **unchanged**                     |
| Tools (`tools/`)               | unchanged                     | **unchanged**                     |
| Session manager                | called from `app.py`          | called from `api/sessions.py`, scoped by `user_id` |
| Scheduler                      | `TaskRunner` started in app   | started in FastAPI lifespan       |
| Knowledge base                 | called from `app.py`          | called from `api/knowledge.py`, per-user namespace |
| **Auth**                       | none                          | **Clerk middleware + JWT verify** |
| **Chat transport**             | `gr.Chatbot` + `yield`        | **WebSocket + structured events** |
| **UI**                         | `app.py` Blocks               | **Next.js `app/` directory**      |
| **Persistence scope**          | one user                      | **per-user (`user_id` column)**   |
| **Hosting**                    | local                         | **Vercel + Fly.io + Clerk**       |

The agent layer never knows the UI changed.

---

## 7 · Proposed repository layout

```
ApexFlow/
├─ agents/                  # ← unchanged
├─ tools/                   # ← unchanged
├─ sandbox/                 # ← becomes sandbox/<user_id>/
├─ sidekick.py              # ← unchanged
├─ session_manager.py       # ← +user_id arg
├─ scheduler.py             # ← +user_id arg
├─ knowledge.py             # ← +user_id namespace
├─ jobs.py / interview.py   # ← +user_id arg
│
├─ api/                     # NEW — FastAPI surface
│  ├─ main.py               # app factory, lifespan, CORS, WS mount
│  ├─ auth.py               # Clerk JWT verification
│  ├─ deps.py               # current_user, sidekick singleton
│  ├─ migrations/           # SQL: add user_id columns
│  ├─ routes/
│  │  ├─ sessions.py        # all routes: Depends(current_user)
│  │  ├─ chat.py            # WS /api/chat/{session_id}?token=
│  │  ├─ tasks.py
│  │  ├─ knowledge.py
│  │  ├─ jobs.py
│  │  └─ interview.py
│  └─ schemas.py
│
├─ web/                     # NEW — Next.js app (deploys to Vercel)
│  ├─ middleware.ts         # Clerk route protection
│  ├─ app/
│  │  ├─ page.tsx           # marketing landing (public)
│  │  ├─ app/page.tsx       # product UI (gated)
│  │  └─ layout.tsx         # ClerkProvider wrapper
│  ├─ components/
│  │  ├─ chat/              # Composer, MessageList, AgentTrace
│  │  ├─ panels/            # SessionsRail, ScheduledTasks, KB, Jobs
│  │  └─ ui/                # shadcn primitives
│  ├─ lib/
│  │  ├─ api.ts             # fetch wrapper that injects Clerk token
│  │  └─ ws.ts              # WS hook with token in query param
│  ├─ styles/globals.css
│  └─ tailwind.config.ts
│
├─ fly.toml                 # NEW — Fly.io deployment config
├─ Dockerfile               # NEW — backend image (Python + Playwright)
├─ docker-compose.yml       # NEW — local dev (api + sandbox)
└─ legacy/app.py            # ← old Gradio app, kept for one release
```

---

## 8 · Phased rollout

Each phase is shippable. You can pause after any of them.

### Phase 0 · Extract the API behind Gradio — ~½ day
Move every helper currently in `app.py` into FastAPI route handlers that
return JSON. Gradio keeps working — it now calls the API internally. This
proves the API surface without touching the UI yet.

### Phase 1 · Marketing page on Vercel — ~1 day
Spin up `web/`. Port `design_proposal.html` to `app/page.tsx`. Push to
Vercel, get a free `*.vercel.app` URL (or attach a custom domain).
**This is the customer-visible win on its own.**

### Phase 2 · Clerk + multi-tenancy — ~1 day
Create the Clerk app, add the middleware, wrap with `<ClerkProvider>`.
Add `user_id` columns + the migration. Add `current_user` dependency to
every API route. Run one local sign-in end-to-end.

### Phase 3 · Backend on Fly.io — ~½ day
Write the Dockerfile (Python + Playwright base image), `fly launch`, attach
a 3 GB persistent volume for the SQLite files and `sandbox/`. Set Clerk
JWKS URL + API keys as Fly secrets. Wire the Vercel project to the new
backend URL via `NEXT_PUBLIC_API_URL`.

### Phase 4 · Product UI (chat surface) — ~2 days
Build `web/app/app/page.tsx`: sessions rail, message list, agent trace,
composer. Wire `lib/ws.ts` to `WS /api/chat/{session_id}`. Stream tokens
straight from `sidekick.run_superstep()`; render trace events as separate
stream frames so the UI shows "→ browser.search(...)" as it happens.

### Phase 5 · Side panels — ~1 day
Sessions, scheduled tasks, knowledge base, jobs, interviews. Each is a
thin React component over an existing endpoint. shadcn Table / Dialog /
Toast handle the heavy lifting.

### Phase 6 · Decommission Gradio — ~½ day
Move `app.py` to `legacy/app.py`, drop the Gradio dep, update the README
with the new local-dev story (`docker compose up`).

**Total**: ~6 working days for one engineer.

---

## 9 · The chat-streaming contract

This is the only non-trivial integration point. Sketch:

```python
# api/routes/chat.py
@router.websocket("/chat/{session_id}")
async def chat(ws: WebSocket, session_id: str):
    await ws.accept()
    user_id = verify_token_from_query(ws)            # Clerk JWT in ?token=
    sidekick = await get_sidekick_for(user_id, session_id)
    while True:
        payload = await ws.receive_json()            # {message, success_criteria}
        async for event in sidekick.run_superstep_events(
            payload["message"], payload.get("success_criteria"),
        ):
            await ws.send_json(event)                # {type: token|trace|final, ...}
```

`run_superstep_events` is a thin wrapper around the existing `run_superstep`
that yields structured events instead of just history snapshots. This is the
one new method to add to `sidekick.py`. The trace events power the inline
"→ browser.search(immobilienscout24)" lines from the design demo.

---

## 10 · Risks & mitigations

| Risk                                       | Mitigation                                              |
|--------------------------------------------|---------------------------------------------------------|
| Vercel ≠ backend host (easy to misread)    | Document the split clearly in README + this file        |
| Fly.io machine sleeps / cold-starts        | Use a paid `auto_stop=false` machine ($3/mo) if it bites |
| Clerk JWT expiry mid-WebSocket             | Reconnect on `token_expired` event, re-issue from `getToken` |
| Cross-tenant leakage in `sandbox/`         | Hard path-prefix check; deny if resolved path escapes user dir |
| SQLite write contention with multi-user    | Acceptable to ~dozens concurrent; plan Postgres swap path |
| Playwright/Chromium image size on Fly      | Use `mcr.microsoft.com/playwright/python` base image    |
| Two stacks to maintain (Py + JS)           | Generate TS types from Pydantic via `datamodel-codegen` |

---

## 11 · The quick decision

- **Weekend portfolio play (1 day)** → Phase 1 only. Ship the marketing
  page on Vercel; keep Gradio as the actual app. Biggest perceived-quality
  jump for the least work.
- **Customer-demo-ready (3–4 days)** → Phases 0 → 3. Frontend on Vercel,
  backend on Fly, Clerk gating `/app`. Now you can give a prospect a real
  URL and a sign-in.
- **Production-ready (~6 days)** → Phases 0 → 6. Replace Gradio entirely,
  retire `app.py`.

My recommendation: **Phase 1 this weekend, Phases 0/2/3 the weekend after.**
That gets you a public, authenticated, hosted product — the artefact a
serious customer needs to see — for ~$5/month all-in.
