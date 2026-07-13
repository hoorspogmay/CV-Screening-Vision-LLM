export default function Navbar() {
  return (
    <header className="navbar">
      <div className="container navbar__inner">
        <div className="navbar__brand">
          <span className="navbar__mark" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="2" width="16" height="16" rx="5" fill="var(--color-primary)" />
              <path
                d="M6 10.2l2.4 2.4L14 7"
                stroke="white"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <div>
            <h1 className="navbar__title">Talent Screen</h1>
            <p className="navbar__subtitle">IT Resume Screening</p>
          </div>
        </div>
      </div>
    </header>
  );
}
