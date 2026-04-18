"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HistoryMessage, SessionInfo } from "@/lib/types";
import { SessionsRail } from "./SessionsRail";
import { ChatView } from "./ChatView";
import { RightRail } from "./RightRail";

export function Workspace() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryMessage[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [toast, setToast] = useState<{ msg: string; kind?: "error" } | null>(
    null
  );
  // Bumped after a chat turn finishes — panels listen and refresh.
  const [refreshTick, setRefreshTick] = useState(0);

  const showError = useCallback((msg: string) => {
    setToast({ msg, kind: "error" });
    window.setTimeout(() => setToast(null), 5000);
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const list = await api.listSessions();
      setSessions(list);
      return list;
    } catch (e) {
      showError(`Failed to load sessions: ${(e as Error).message}`);
      return [];
    }
  }, [showError]);

  const switchSession = useCallback(
    async (id: string) => {
      setActiveId(id);
      setLoadingHistory(true);
      setHistory([]);
      try {
        const h = await api.getHistory(id);
        setHistory(h);
      } catch (e) {
        showError(`Failed to load history: ${(e as Error).message}`);
      } finally {
        setLoadingHistory(false);
      }
    },
    [showError]
  );

  // First-mount bootstrap: ensure a session exists, load it.
  useEffect(() => {
    (async () => {
      try {
        const latest = await api.latestSession();
        const list = await loadSessions();
        await switchSession(
          list.find((s) => s.id === latest.id)?.id ?? latest.id
        );
      } catch (e) {
        showError(`Could not reach API: ${(e as Error).message}`);
      }
    })();
  }, [loadSessions, switchSession, showError]);

  const createSession = async () => {
    try {
      const s = await api.createSession();
      const list = await loadSessions();
      await switchSession(s.id);
      void list;
    } catch (e) {
      showError(`Create failed: ${(e as Error).message}`);
    }
  };

  const renameSession = async (id: string, name: string) => {
    try {
      await api.renameSession(id, name);
      await loadSessions();
    } catch (e) {
      showError(`Rename failed: ${(e as Error).message}`);
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      const list = await loadSessions();
      const fallback =
        list.find((s) => s.id !== id)?.id ?? (await api.latestSession()).id;
      await switchSession(fallback);
    } catch (e) {
      showError(`Delete failed: ${(e as Error).message}`);
    }
  };

  const onTurnComplete = useCallback(() => {
    setRefreshTick((t) => t + 1);
  }, []);

  const active = sessions.find((s) => s.id === activeId) ?? null;

  return (
    <>
      <header className="app-bar">
        <div className="brand">
          <div className="mark">A</div>
          <div className="name">
            Apex<em>Flow</em>
          </div>
        </div>

        <div className="session-pill">
          <div className="ring" />
          <span>Active</span>
          <span className="name">{active?.name ?? "—"}</span>
        </div>

        <div className="right-meta">
          <a href="/" title="Back to landing">
            ↩ Landing
          </a>
        </div>
      </header>

      <SessionsRail
        sessions={sessions}
        activeId={activeId}
        onSelect={switchSession}
        onCreate={createSession}
        onRename={renameSession}
        onDelete={deleteSession}
      />

      <ChatView
        sessionId={activeId}
        history={history}
        setHistory={setHistory}
        loadingHistory={loadingHistory}
        onError={showError}
        onTurnComplete={onTurnComplete}
      />

      <RightRail refreshTick={refreshTick} onError={showError} />

      {toast && (
        <div className={`toast ${toast.kind ?? ""}`}>{toast.msg}</div>
      )}
    </>
  );
}
