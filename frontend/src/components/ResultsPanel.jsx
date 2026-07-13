import CandidateCard from "./CandidateCard.jsx";
import SkeletonCard from "./SkeletonCard.jsx";
import EmptyState from "./EmptyState.jsx";

export default function ResultsPanel({ title, variant, results, pendingCount, status }) {
  const isIdle = status === "idle";

  return (
    <section className={`results-panel results-panel--${variant}`} aria-label={title}>
      <div className="results-panel__header">
        <h3>{title}</h3>
        <span className="results-panel__count">{results.length}</span>
      </div>

      <div className="results-panel__list">
        {isIdle && results.length === 0 && (
          <EmptyState
            title={`No ${title.toLowerCase()} yet`}
            subtitle="Upload resumes and start screening to see results here."
          />
        )}

        {results.map((result) => (
          <CandidateCard key={result.file_id} result={result} />
        ))}

        {!isIdle &&
          Array.from({ length: pendingCount }).map((_, i) => <SkeletonCard key={`skeleton-${variant}-${i}`} />)}

        {!isIdle && results.length === 0 && pendingCount === 0 && status === "completed" && (
          <EmptyState title={`No ${title.toLowerCase()}`} subtitle="No candidates fell into this category." />
        )}
      </div>
    </section>
  );
}
