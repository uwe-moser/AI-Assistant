export function Author() {
  return (
    <section className="author reveal" id="author">
      <div className="wrap">
        <div className="author-grid">
          <div>
            <h2>
              Designed and engineered
              <br />
              by <em>Uwe Moser</em>.
            </h2>
            <p>
              ApexFlow is my reference build for serious multi-agent work — the
              kind of system I help teams design, ship and operate. If
              you&apos;re prototyping an internal copilot, an automation fabric
              or a customer-facing agent, this is the conversation worth having.
            </p>
            <div className="cta-row" style={{ marginTop: 36 }}>
              <a className="btn btn-primary" href="mailto:blu_ray@web.de">
                Start a conversation
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </a>
              <a
                className="btn btn-ghost"
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
              >
                View the source
              </a>
            </div>
          </div>

          <aside className="quote-card">
            <div className="q-mark">&ldquo;</div>
            <blockquote>
              The interesting question isn&apos;t whether one model can answer a
              question. It&apos;s whether a system of agents can deliver an
              outcome — reliably, observably, on budget.
            </blockquote>
            <div className="who">
              <div className="av">U</div>
              <div>
                <div style={{ color: "var(--bone)" }}>Uwe Moser</div>
                <div>Engineer · Berlin</div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
