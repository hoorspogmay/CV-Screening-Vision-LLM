export default function CandidateCard({ result }) {
  const hasError = Boolean(result.error);
  const decision = hasError ? "ERROR" : result.decision;
  const score = typeof result.match_score === "number" ? result.match_score : null;
  const routedJobs = Array.isArray(result.routed_job_titles) ? result.routed_job_titles.filter(Boolean) : [];
  const routingLabel = routedJobs.length > 0
    ? `Routed to: ${routedJobs.join(" • ")}`
    : decision === "REJECT"
      ? "No clear job match detected"
      : null;

  const cardClass = decision === "ACCEPT"
    ? "candidate-card--accept"
    : decision === "DOUBTFUL"
      ? "candidate-card--doubtful"
      : decision === "REJECT"
        ? "candidate-card--reject"
        : "candidate-card--error";

  const scoreLabel = score !== null ? `${Math.round(score)}%` : "--";
  const routingText = routingLabel;

  return (
    <article className={`candidate-card ${cardClass}`}>
      <div className="candidate-card__header">
        <div>
          <h4 className="candidate-card__name">{result.candidate_name || "Unknown Candidate"}</h4>
          <p className="candidate-card__file">{result.file_name}</p>
        </div>
        <div className="candidate-card__meta">
          <span className="candidate-card__score-value">{scoreLabel}</span>
        </div>
      </div>

      <div className="candidate-card__gauge">
        <div className="candidate-card__gauge-track">
          <div className={`candidate-card__gauge-fill candidate-card__gauge-fill--${decision.toLowerCase()}`} style={{ width: score !== null ? `${Math.max(0, Math.min(score, 100))}%` : "0%" }} />
        </div>
      </div>

      {!hasError && score !== null ? (
        <p className="candidate-card__requirements">{Math.round((score / 100) * 9)} / 9 requirements met</p>
      ) : null}

      {routingText ? <p className="candidate-card__routing">{routingText}</p> : null}

      {hasError ? (
        <p className="candidate-card__error">Could not process this resume: {result.error}</p>
      ) : null}
    </article>
  );
}
