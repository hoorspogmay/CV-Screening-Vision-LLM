export default function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="skeleton-card__row">
        <div className="skeleton-line skeleton-line--title" />
        <div className="skeleton-pill" />
      </div>
      <div className="skeleton-line skeleton-line--sm" />
      <div className="skeleton-line skeleton-line--sm" />
      <div className="skeleton-line skeleton-line--sm" />
    </div>
  );
}
