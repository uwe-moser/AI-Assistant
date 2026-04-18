export function Demo() {
  return (
    <section className="demo reveal" id="demo">
      <div className="wrap">
        <div className="sec-head">
          <div>
            <div className="sec-num">§ 03 — In motion</div>
            <h2>
              One prompt. <em>Many agents</em>. A traceable result.
            </h2>
          </div>
          <p>
            Here&apos;s what an actual superstep looks like: the orchestrator
            decomposes the request, dispatches in parallel, gathers evidence, and
            answers — with the trace visible at every step.
          </p>
        </div>

        <div className="demo-shell">
          <div className="demo-bar">
            <span className="dot-r"></span>
            <span className="dot-r"></span>
            <span className="dot-r"></span>
            <span className="title">
              apexflow · session: berlin-relocation · superstep #14
            </span>
          </div>
          <div className="demo-body">
            <aside className="demo-side">
              <h5>Sessions</h5>
              <div className="ses active">
                <span>Berlin relocation</span>
                <span className="when">now</span>
              </div>
              <div className="ses">
                <span>Q1 hiring research</span>
                <span className="when">2d</span>
              </div>
              <div className="ses">
                <span>arXiv weekly digest</span>
                <span className="when">1w</span>
              </div>
              <div className="ses">
                <span>Apartment shortlist</span>
                <span className="when">2w</span>
              </div>
              <h5 style={{ marginTop: 32 }}>Scheduled</h5>
              <div className="ses">
                <span>arXiv · daily 08:00</span>
                <span className="when">cron</span>
              </div>
              <div className="ses">
                <span>Job watch · 4h</span>
                <span className="when">cron</span>
              </div>
            </aside>

            <div className="demo-chat">
              <div className="msg user">
                <div className="av">U</div>
                <div className="body">
                  Find three apartments in Prenzlauer Berg under €2 200, walking
                  distance to a daycare, then summarise the daycare reviews and
                  schedule a recap for Friday at 9.
                </div>
              </div>

              <div className="msg bot">
                <div className="av">A</div>
                <div className="body">
                  <div style={{ marginBottom: 10 }}>
                    <span className="tag">Browser</span>
                    <span className="tag">Location</span>
                    <span className="tag">Research</span>
                    <span className="tag">System</span>
                  </div>
                  <strong>Three candidates that match your constraints:</strong>
                  <div className="agent-trace">
                    <div>
                      <span className="arrow">→</span> orchestrator.plan() · 4
                      sub-tasks identified
                    </div>
                    <div>
                      <span className="arrow">→</span>{" "}
                      browser.search(immobilienscout24) · 47 listings · filtered →
                      3
                    </div>
                    <div>
                      <span className="arrow">→</span> location.nearby(daycare,
                      600m) · 8 facilities
                    </div>
                    <div>
                      <span className="arrow">→</span>{" "}
                      research.reviews(google_maps) · 142 reviews · summarised
                    </div>
                    <div>
                      <span className="arrow">→</span>{" "}
                      system.schedule(&quot;Friday 09:00&quot;) · cron set ·
                      pushover armed
                    </div>
                    <div>
                      <span className="arrow">→</span> evaluate(success_criteria)
                      · ✓ passed
                    </div>
                  </div>
                  <p
                    style={{
                      marginTop: 14,
                      color: "var(--bone-2)",
                      fontSize: 14,
                      lineHeight: 1.6,
                    }}
                  >
                    <strong>1. Schönhauser Allee 124</strong> — €1 980, 380m to
                    Kita Sonnenschein (4.6★, &quot;warm staff, good food&quot;).
                    <br />
                    <strong>2. Stargarder Straße 7</strong> — €2 150, 510m to Kita
                    Pfefferwerk (4.4★, &quot;creative program&quot;).
                    <br />
                    <strong>3. Greifenhagener 18</strong> — €2 090, 290m to Kita
                    Wichtelhaus (4.7★, &quot;small groups, bilingual&quot;).
                  </p>
                  <p style={{ marginTop: 12, color: "var(--muted)", fontSize: 13 }}>
                    Recap scheduled for{" "}
                    <em
                      style={{
                        color: "var(--accent)",
                        fontStyle: "italic",
                        fontFamily: "var(--serif)",
                      }}
                    >
                      Fri 09:00
                    </em>
                    . I&apos;ll re-check listings and notify you if any drop.
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="composer">
            <input placeholder="Ask anything — or hand off a project…" />
            <span className="mono" style={{ color: "var(--muted-2)" }}>
              ⌘ ↵
            </span>
            <button className="go">Dispatch</button>
          </div>
        </div>
      </div>
    </section>
  );
}
