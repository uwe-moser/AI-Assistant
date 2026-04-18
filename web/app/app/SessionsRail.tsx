"use client";

import { useState } from "react";
import type { SessionInfo } from "@/lib/types";

type Props = {
  sessions: SessionInfo[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
};

function formatWhen(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SessionsRail({
  sessions,
  activeId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: Props) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const startRename = (s: SessionInfo) => {
    setRenamingId(s.id);
    setRenameValue(s.name);
  };

  const commitRename = () => {
    if (renamingId && renameValue.trim()) {
      onRename(renamingId, renameValue.trim());
    }
    setRenamingId(null);
  };

  return (
    <aside className="rail">
      <div className="rail-head">
        <h5>Sessions</h5>
        <span className="mono" style={{ fontSize: 10 }}>
          {sessions.length}
        </span>
      </div>

      <button className="new-btn" onClick={onCreate}>
        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 5v14M5 12h14" />
        </svg>
        New session
      </button>

      <div className="rail-list">
        {sessions.map((s) => {
          const isActive = s.id === activeId;
          const isRenaming = renamingId === s.id;

          return (
            <div
              key={s.id}
              className={`session ${isActive ? "active" : ""}`}
              onClick={() => !isRenaming && onSelect(s.id)}
            >
              <div className="row1">
                {isRenaming ? (
                  <input
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={commitRename}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename();
                      if (e.key === "Escape") setRenamingId(null);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      flex: 1,
                      background: "var(--ink-3)",
                      border: "1px solid var(--accent)",
                      borderRadius: 6,
                      color: "var(--bone)",
                      padding: "4px 8px",
                      fontSize: 13,
                      fontFamily: "var(--serif)",
                      outline: 0,
                    }}
                  />
                ) : (
                  <span className="name">{s.name}</span>
                )}

                <div className="actions">
                  <button
                    className="icon-btn"
                    title="Rename"
                    onClick={(e) => {
                      e.stopPropagation();
                      startRename(s);
                    }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z" />
                    </svg>
                  </button>
                  <button
                    className="icon-btn"
                    title="Delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (
                        window.confirm(`Delete session "${s.name}"? This wipes its chat history.`)
                      ) {
                        onDelete(s.id);
                      }
                    }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z" />
                    </svg>
                  </button>
                </div>
              </div>
              <div className="when">{formatWhen(s.created_at)}</div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
