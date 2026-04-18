# ApexFlow API

FastAPI surface for the ApexFlow multi-agent assistant. Wraps the existing
Sidekick orchestrator, scheduler, knowledge base, jobs, and interview modules
so the new Next.js frontend in [`web/`](../web) can drive everything over HTTP
and WebSocket.

The legacy Gradio app keeps working — `python app.py` is unaffected.

## Run

From the project root:

```bash
uvicorn api.main:app --reload --port 8000
```

Interactive docs: <http://localhost:8000/docs>.

The Next.js dev server expects this on port 8000 (CORS is open to
`localhost:3000` and `127.0.0.1:3000`).

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness probe |
| GET | `/api/sessions` | List chat sessions |
| POST | `/api/sessions` | Create a session |
| GET | `/api/sessions/latest` | Get/create most recent session |
| PATCH | `/api/sessions/{id}` | Rename a session |
| DELETE | `/api/sessions/{id}` | Delete a session + its history |
| GET | `/api/sessions/{id}/history` | Persisted user/assistant messages |
| WS | `/api/ws/chat/{session_id}` | Streaming chat (see protocol below) |
| GET | `/api/tasks` | List scheduled tasks |
| DELETE | `/api/tasks/{id}` | Cancel a scheduled task |
| GET | `/api/knowledge` | KB overview (chunks per file) |
| POST | `/api/knowledge/upload` | Multipart upload + index |
| POST | `/api/knowledge/reindex` | Re-scan KB directory |
| DELETE | `/api/knowledge/{filename}` | Remove a document |
| GET | `/api/jobs/statuses` | Allowed pipeline statuses |
| GET | `/api/jobs?status=` | List jobs (optional status filter) |
| GET | `/api/jobs/profile` | Candidate profile |
| GET | `/api/jobs/{id}` | Single job |
| PATCH | `/api/jobs/{id}/status` | Move a job through the pipeline |
| GET | `/api/interviews` | List interview sessions |
| GET | `/api/interviews/{id}` | Session + all turns |

## Chat WebSocket protocol

Open `ws://localhost:8000/api/ws/chat/{session_id}`. The Sidekick is created
lazily on the first connection per session and held in memory for reuse.

Send (one frame per turn):

```json
{
  "message": "research recent tax filing deadlines",
  "success_criteria": "",
  "history": [{"role": "user", "content": "..."}]
}
```

Receive — multiple frames per turn:

```json
{"type": "history", "history": [/* full updated history */]}
{"type": "history", "history": [/* ...next snapshot... */]}
{"type": "done"}
```

Tool delegations and tool results show up inside `history` as assistant
messages with a `metadata.title` of `"🤖 Delegating to: <agent>"` or
`"📋 Result: <agent>"` — the frontend can render these as a collapsible
agent-trace inline with the conversation.

Errors arrive as `{"type": "error", "error": "<message>"}` and the socket
stays open so the next turn can still be sent.

## What's intentionally not here yet

- **Auth.** No Clerk, no per-user scoping. Every request hits the same
  shared SQLite instance. Multi-tenancy is the next layer.
- **Job search write paths.** `POST /api/jobs/search`, profile uploads,
  CV/cover-letter generation — these all run through the chat agents today,
  so the WebSocket already covers them.
- **Interview write paths.** Same reason: starting and answering questions
  is driven by the InterviewCoachAgent over the chat socket.
