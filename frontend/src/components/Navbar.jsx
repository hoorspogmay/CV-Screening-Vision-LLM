export default function Navbar() {
  return (
    <header className="navbar">
      <div className="container navbar__inner">
        <div className="navbar__brand">
          <span className="navbar__mark" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14" stroke="white" strokeWidth="2" />
              <path d="M5 12h14" stroke="white" strokeWidth="2" />
              <path d="M17 7L21 7" stroke="white" strokeWidth="2" strokeLinecap="round" />
              <path d="M7 17L3 17" stroke="white" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          <div>
            <h1 className="navbar__title">Talent Screen</h1>
            <p className="navbar__subtitle">Production-grade resume screening</p>
          </div>
        </div>
        <div className="navbar__actions">
          <button type="button" className="btn btn--outline-signal">Dark mode</button>
        </div>
      </div>
    </header>
  );
}
