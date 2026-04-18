export function Hero() {
  return (
    <header className="hero">
      <div className="wrap">
        <div className="hero-grid">
          <div>
            <div className="eyebrow">
              <span className="dot"></span> A multi-agent system · v0.4 · 2026
            </div>
            <h1 className="headline">
              Eight specialists.
              <br />
              <em>One</em> orchestrator.
              <br />
              <span className="thin">Zero compromise.</span>
            </h1>
            <p className="lede" style={{ marginTop: 42 }}>
              ApexFlow is a hierarchical, multi-agent assistant that{" "}
              <strong>
                thinks, browses, executes and reasons over your private knowledge
              </strong>{" "}
              — running entirely on your machine. Built to demonstrate
              production-grade agent orchestration with LangGraph, Playwright and
              ChromaDB.
            </p>
            <div className="cta-row">
              <a className="btn btn-primary" href="/app">
                Open the workspace
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </a>
              <a className="btn btn-ghost" href="#demo">
                Watch the demo
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </a>
            </div>
          </div>

          <aside className="status-card" aria-label="Live status">
            <div className="status-title">
              <b>orchestrator.live</b>
              <span className="ring" aria-hidden="true"></span>
            </div>
            <div className="status-row">
              <span className="k">Active agents</span>
              <span className="v">8 / 8</span>
            </div>
            <div className="status-row">
              <span className="k">Avg superstep</span>
              <span className="v">2.4 s</span>
            </div>
            <div className="status-row">
              <span className="k">Tool calls / hr</span>
              <span className="v">1 312</span>
            </div>
            <div className="status-row">
              <span className="k">Knowledge corpus</span>
              <span className="v">142 docs · 8.4k chunks</span>
            </div>
            <div className="status-row">
              <span className="k">Sandbox</span>
              <span className="v">isolated · docker</span>
            </div>
            <div className="status-row">
              <span className="k">Trace</span>
              <span className="v" style={{ color: "var(--accent)" }}>
                recording →
              </span>
            </div>
          </aside>
        </div>
      </div>
    </header>
  );
}
