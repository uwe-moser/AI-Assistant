import sqlite3
import json

from config import DB_PATH, CHECKPOINTS_DB_PATH

# ── Chat History ──────────────────────────────────────────────────────────────
print("=" * 60)
print(f"CHAT HISTORY  ({DB_PATH})")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
rows = conn.execute("SELECT id, session_id, message FROM message_store ORDER BY id").fetchall()
conn.close()

for id_, session_id, raw in rows:
    msg = json.loads(raw)
    role = msg.get("type", "?").upper()
    content = msg.get("data", {}).get("content", "")
    print(f"[{id_}] {role}: {content}\n")

# ── Checkpoints ───────────────────────────────────────────────────────────────
print("=" * 60)
print(f"CHECKPOINTS  ({CHECKPOINTS_DB_PATH})")
print("=" * 60)

conn = sqlite3.connect(CHECKPOINTS_DB_PATH)
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