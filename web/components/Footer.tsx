export function Footer() {
  return (
    <footer>
      <div className="wrap">
        <div className="rule" style={{ marginBottom: 36 }}></div>
        <div className="foot-row">
          <div className="brand">
            <div className="mark">A</div>
            <div className="name">
              Apex<em>Flow</em>
            </div>
          </div>
          <div className="links">
            <a href="#architecture">Architecture</a>
            <a href="#agents">Agents</a>
            <a href="#demo">Demo</a>
            <a href="https://github.com" target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
            <a href="mailto:blu_ray@web.de">Contact</a>
          </div>
        </div>
        <div className="colophon">
          © 2026 Uwe Moser · Set in Fraunces, Instrument Sans &amp; JetBrains Mono
          · Built with care, not templates
        </div>
      </div>
    </footer>
  );
}
