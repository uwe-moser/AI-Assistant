"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatFrame, HistoryMessage } from "@/lib/types";

type Props = {
  sessionId: string | null;
  history: HistoryMessage[];
  setHistory: (h: HistoryMessage[]) => void;
  loadingHistory: boolean;
  onError: (msg: string) => void;
  onTurnComplete: () => void;
};

type ConnState = "offline" | "live" | "thinking";

export function ChatView({
  sessionId,
  history,
  setHistory,
  loadingHistory,
  onError,
  onTurnComplete,
}: Props) {
  const [input, setInput] = useState("");
  const [criteria, setCriteria] = useState("");
  const [conn, setConn] = useState<ConnState>("offline");
  const [busy, setBusy] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const streamEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Open / re-open the WebSocket whenever the session changes.
  useEffect(() => {
    if (!sessionId) return;
    const url = `${api.wsBase()}/api/ws/chat/${sessionId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConn("live");
    ws.onclose = () => setConn("offline");
    ws.onerror = () => onError("WebSocket error — is the API running on :8000?");

    ws.onmessage = (event) => {
      let frame: ChatFrame;
      try {
        frame = JSON.parse(event.data);
      } catch {
        return;
      }
      if (frame.type === "history") {
        setHistory(frame.history);
      } else if (frame.type === "done") {
        setConn("live");
        setBusy(false);
        onTurnComplete();
      } else if (frame.type === "error") {
        onError(frame.error);
        setConn("live");
        setBusy(false);
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
    // setHistory is stable enough; intentionally not in deps to avoid reconnect storms
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Auto-scroll on new content.
  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history.length, history[history.length - 1]?.content]);

  // Auto-grow the textarea.
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [input]);

  const send = () => {
    const trimmed = input.trim();
    if (!trimmed || !sessionId) return;
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      onError("Not connected — please wait a moment and retry.");
      return;
    }
    ws.send(
      JSON.stringify({
        message: trimmed,
        success_criteria: criteria.trim(),
        history,
      })
    );
    setInput("");
    setBusy(true);
    setConn("thinking");
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <main className="chat">
      <div className="chat-stream">
        {loadingHistory ? null : history.length === 0 ? (
          <div className="empty-state">
            <h3>
              A new <em>conversation</em>.
            </h3>
            <p>
              Ask anything. The orchestrator routes to specialists — research,
              browser, documents, knowledge, jobs and more — and streams
              progress back as it works.
            </p>
          </div>
        ) : (
          history.map((m, i) => <Message key={i} m={m} />)
        )}
        <div ref={streamEndRef} />
      </div>

      <div className="composer">
        <div className="criteria-row">
          <span className="label">Criteria</span>
          <input
            placeholder="(optional) success criteria — adds an evaluator loop"
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
          />
          <ConnIndicator state={conn} />
        </div>
        <div className="input-row">
          <textarea
            ref={textareaRef}
            placeholder="Send a message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            rows={1}
          />
          <button
            className="send"
            onClick={send}
            disabled={busy || !input.trim() || !sessionId}
          >
            {busy ? "Working" : "Send"}
          </button>
        </div>
      </div>
    </main>
  );
}

function Message({ m }: { m: HistoryMessage }) {
  const title = m.metadata?.title;
  if (title) {
    return (
      <div className="trace">
        <div className="head">
          <span className="arrow">→</span>
          <span>{title}</span>
        </div>
        <div className="body">{m.content}</div>
      </div>
    );
  }
  return (
    <div className={`bubble ${m.role}`}>
      <div className="av">{m.role === "user" ? "U" : "A"}</div>
      <div className="body">{m.content}</div>
    </div>
  );
}

function ConnIndicator({ state }: { state: ConnState }) {
  const label =
    state === "live" ? "Connected" : state === "thinking" ? "Thinking" : "Offline";
  return (
    <span className={`conn-status ${state}`}>
      <span className="dot" />
      {label}
    </span>
  );
}
