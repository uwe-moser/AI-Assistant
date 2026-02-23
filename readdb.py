import sqlite3
import json

# ── Chat History ──────────────────────────────────────────────────────────────
print("=" * 60)
print("CHAT HISTORY  (sidekick_chat_history.db)")
print("=" * 60)

conn = sqlite3.connect("sidekick_chat_history.db")
rows = conn.execute("SELECT id, session_id, message FROM message_store ORDER BY id").fetchall()
conn.close()

for id_, session_id, raw in rows:
    msg = json.loads(raw)
    role = msg.get("type", "?").upper()
    content = msg.get("data", {}).get("content", "")
    print(f"[{id_}] {role}: {content}\n")

# ── Checkpoints ───────────────────────────────────────────────────────────────
print("=" * 60)
print("CHECKPOINTS  (sidekick_checkpoints.db)")
print("=" * 60)

conn = sqlite3.connect("sidekick_checkpoints.db")
rows = conn.execute(
    "SELECT thread_id, checkpoint_id, parent_checkpoint_id FROM checkpoints ORDER BY checkpoint_id"
).fetchall()
count = conn.execute("SELECT COUNT(*) FROM writes").fetchone()[0]
conn.close()

for thread_id, checkpoint_id, parent_id in rows:
    parent = parent_id or "ROOT"
    print(f"thread : {thread_id}")
    print(f"  id   : {checkpoint_id}")
    print(f"  parent: {parent}\n")

print(f"Total writes across all checkpoints: {count}")