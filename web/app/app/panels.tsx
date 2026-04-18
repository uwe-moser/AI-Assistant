"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  InterviewSessionDetail,
  InterviewSessionInfo,
  JobInfo,
  KnowledgeOverview,
  ScheduledTaskInfo,
} from "@/lib/types";

type PanelProps = {
  refreshTick: number;
  onError: (msg: string) => void;
};

function formatWhen(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function PanelHead({
  title,
  countText,
  children,
}: {
  title: string;
  countText: string;
  children?: React.ReactNode;
}) {
  return (
    <>
      <div className="panel-head">
        <h4>{title}</h4>
        <span className="count">{countText}</span>
      </div>
      {children}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Tasks
// ─────────────────────────────────────────────────────────────────────

export function TasksPanel({ refreshTick, onError }: PanelProps) {
  const [tasks, setTasks] = useState<ScheduledTaskInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setTasks(await api.listTasks());
    } catch (e) {
      onError(`Tasks: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    reload();
  }, [reload, refreshTick]);

  const cancel = async (id: string) => {
    if (!window.confirm(`Cancel scheduled task ${id}?`)) return;
    try {
      await api.cancelTask(id);
      reload();
    } catch (e) {
      onError(`Cancel failed: ${(e as Error).message}`);
    }
  };

  return (
    <div className="panel">
      <PanelHead title="Scheduled" countText={`${tasks.length} task${tasks.length === 1 ? "" : "s"}`} />

      {loading ? null : tasks.length === 0 ? (
        <div className="panel-empty">
          No scheduled tasks. Ask the assistant to schedule something.
        </div>
      ) : (
        tasks.map((t) => (
          <div key={t.id} className="panel-row">
            <div className="row-top">
              <div className="title">{t.description}</div>
              <button
                className="row-action danger"
                onClick={() => cancel(t.id)}
              >
                Cancel
              </button>
            </div>
            <div className="sub">
              <span className="badge">{t.cron_expr}</span>
              <span className={t.enabled ? "" : "neutral"}>
                {t.enabled ? "Enabled" : "Disabled"}
              </span>
              {t.notify && <span>Push on</span>}
              <span className="neutral">Last run: {formatWhen(t.last_run)}</span>
            </div>
            {t.last_result && (
              <div className="desc" style={{ opacity: 0.85 }}>
                {t.last_result.length > 220
                  ? t.last_result.slice(0, 220) + "…"
                  : t.last_result}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Knowledge
// ─────────────────────────────────────────────────────────────────────

export function KnowledgePanel({ refreshTick, onError }: PanelProps) {
  const [overview, setOverview] = useState<KnowledgeOverview | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string>("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  const reload = useCallback(async () => {
    try {
      setOverview(await api.knowledge());
    } catch (e) {
      onError(`Knowledge: ${(e as Error).message}`);
    }
  }, [onError]);

  useEffect(() => {
    reload();
  }, [reload, refreshTick]);

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setBusy(true);
    try {
      const res = await api.uploadKnowledge(files);
      setOverview(res.overview);
      setStatusMsg(res.message);
    } catch (e) {
      onError(`Upload failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const reindex = async () => {
    setBusy(true);
    try {
      const res = await api.reindexKnowledge();
      setOverview(res.overview);
      setStatusMsg(res.message);
    } catch (e) {
      onError(`Reindex failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (filename: string) => {
    if (!window.confirm(`Remove '${filename}' from knowledge base?`)) return;
    try {
      const res = await api.deleteKnowledge(filename);
      setOverview(res.overview);
      setStatusMsg(res.message);
    } catch (e) {
      onError(`Delete failed: ${(e as Error).message}`);
    }
  };

  return (
    <div className="panel">
      <PanelHead
        title="Knowledge"
        countText={
          overview ? `${overview.total_chunks} chunk${overview.total_chunks === 1 ? "" : "s"}` : "—"
        }
      />

      <div
        className={`upload-zone ${drag ? "drag" : ""}`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          upload(Array.from(e.dataTransfer.files));
        }}
      >
        {busy ? "Working…" : "Drop PDFs / TXT / MD / CSV — or click to upload"}
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.csv"
          style={{ display: "none" }}
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            upload(files);
            e.target.value = "";
          }}
        />
      </div>

      <div className="panel-button-row">
        <button onClick={reindex} disabled={busy}>
          Reindex all
        </button>
      </div>

      {statusMsg && (
        <div className="panel-row" style={{ background: "var(--ink-3)" }}>
          <div className="desc" style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
            {statusMsg}
          </div>
        </div>
      )}

      {(overview?.documents ?? []).length === 0 ? (
        <div className="panel-empty">No documents indexed yet.</div>
      ) : (
        overview!.documents.map((d) => (
          <div key={d.filename} className="panel-row">
            <div className="row-top">
              <div className="title">{d.filename}</div>
              <button
                className="row-action danger"
                onClick={() => remove(d.filename)}
              >
                Remove
              </button>
            </div>
            <div className="sub">
              <span className="badge">{d.chunks} chunks</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Jobs
// ─────────────────────────────────────────────────────────────────────

export function JobsPanel({ refreshTick, onError }: PanelProps) {
  const [statuses, setStatuses] = useState<string[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.jobStatuses().then(setStatuses).catch((e: Error) => onError(e.message));
  }, [onError]);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setJobs(await api.listJobs(filter || undefined));
    } catch (e) {
      onError(`Jobs: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [filter, onError]);

  useEffect(() => {
    reload();
  }, [reload, refreshTick]);

  return (
    <div className="panel">
      <PanelHead
        title="Pipeline"
        countText={`${jobs.length} job${jobs.length === 1 ? "" : "s"}`}
      />

      <div className="filter-row">
        <button
          className={`filter-pill ${filter === "" ? "active" : ""}`}
          onClick={() => setFilter("")}
        >
          All
        </button>
        {statuses.map((s) => (
          <button
            key={s}
            className={`filter-pill ${filter === s ? "active" : ""}`}
            onClick={() => setFilter(s)}
          >
            {s.replace("_", " ")}
          </button>
        ))}
      </div>

      {loading ? null : jobs.length === 0 ? (
        <div className="panel-empty">
          No jobs in this view. Ask the assistant to search Adzuna or LinkedIn.
        </div>
      ) : (
        jobs.map((j) => (
          <div key={j.id} className="panel-row">
            <div className="row-top">
              <div className="title">{j.title}</div>
              {j.match_score != null && (
                <span className="meta">{Math.round(j.match_score * 100)}%</span>
              )}
            </div>
            <div className="sub">
              {j.company && <span>{j.company}</span>}
              {j.location && <span className="neutral">{j.location}</span>}
              <span className="badge">{j.status.replace("_", " ")}</span>
              <span className="neutral">{j.source}</span>
            </div>
            {j.match_rationale && (
              <div className="desc" style={{ opacity: 0.85 }}>
                {j.match_rationale}
              </div>
            )}
            {j.apply_url && (
              <div className="row-top">
                <a
                  className="row-action"
                  href={j.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open posting ↗
                </a>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Interviews
// ─────────────────────────────────────────────────────────────────────

export function InterviewsPanel({ refreshTick, onError }: PanelProps) {
  const [sessions, setSessions] = useState<InterviewSessionInfo[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<InterviewSessionDetail | null>(null);

  const reload = useCallback(async () => {
    try {
      setSessions(await api.listInterviews());
    } catch (e) {
      onError(`Interviews: ${(e as Error).message}`);
    }
  }, [onError]);

  useEffect(() => {
    reload();
  }, [reload, refreshTick]);

  const open = async (id: string) => {
    if (openId === id) {
      setOpenId(null);
      setDetail(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    try {
      setDetail(await api.getInterview(id));
    } catch (e) {
      onError(`Interview detail: ${(e as Error).message}`);
    }
  };

  return (
    <div className="panel">
      <PanelHead
        title="Practice"
        countText={`${sessions.length} session${sessions.length === 1 ? "" : "s"}`}
      />

      {sessions.length === 0 ? (
        <div className="panel-empty">
          No interview sessions yet. Ask the assistant to start one for a job in the pipeline.
        </div>
      ) : (
        sessions.map((s) => (
          <div key={s.id} className="panel-row">
            <div className="row-top">
              <div className="title">{s.title || `Interview ${s.id}`}</div>
              <button className="row-action" onClick={() => open(s.id)}>
                {openId === s.id ? "Hide" : "View"}
              </button>
            </div>
            <div className="sub">
              <span className="badge">{s.status.replace("_", " ")}</span>
              {s.overall_score != null && (
                <span>{s.overall_score.toFixed(1)} / 5</span>
              )}
              <span className="neutral">{formatWhen(s.created_at)}</span>
            </div>
            {openId === s.id && detail && (
              <div className="desc" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {s.final_summary && (
                  <div style={{ fontStyle: "italic", color: "var(--bone-2)" }}>
                    {s.final_summary}
                  </div>
                )}
                {detail.turns.map((t) => (
                  <div
                    key={t.id}
                    style={{
                      borderTop: "1px dashed var(--line)",
                      paddingTop: 8,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ color: "var(--bone)", fontWeight: 500 }}>
                      Q{t.idx + 1}. {t.question}
                    </div>
                    {t.answer && (
                      <div style={{ marginTop: 4, color: "var(--bone-2)" }}>
                        <span style={{ color: "var(--muted)" }}>A: </span>
                        {t.answer}
                      </div>
                    )}
                    {t.score != null && (
                      <div
                        style={{
                          marginTop: 4,
                          fontFamily: "var(--mono)",
                          fontSize: 10,
                          color: "var(--accent)",
                          letterSpacing: ".1em",
                          textTransform: "uppercase",
                        }}
                      >
                        Score {t.score.toFixed(1)}
                        {t.critique ? ` · ${t.critique}` : ""}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
