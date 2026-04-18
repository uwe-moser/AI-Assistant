export function Nav() {
  return (
    <nav className="top">
      <div className="wrap nav-inner">
        <div className="brand">
          <div className="mark">A</div>
          <div className="name">
            Apex<em>Flow</em>
          </div>
        </div>
        <div className="nav-meta">
          <a href="#architecture">Architecture</a>
          <a href="#agents">Agents</a>
          <a href="#demo">Demo</a>
          <a href="#author">Engineer</a>
          <a className="nav-cta" href="/app">
            Open Workspace →
          </a>
        </div>
      </div>
    </nav>
  );
}
