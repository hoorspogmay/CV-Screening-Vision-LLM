export default function EmptyState({ title, subtitle }) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <rect x="4" y="3" width="20" height="22" rx="3" stroke="var(--color-text-tertiary)" strokeWidth="1.6" />
          <path d="M9 10h10M9 14h10M9 18h6" stroke="var(--color-text-tertiary)" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </div>
      <p className="empty-state__title">{title}</p>
      <p className="empty-state__subtitle">{subtitle}</p>
    </div>
  );
}
