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

  const badgeClass = decision === "ACCEPT"
    ? "badge--accept"
    : decision === "DOUBTFUL"
      ? "badge--doubtful"
      : decision === "REJECT"
        ? "badge--reject"
        : "badge--error";

  const badgeLabel = decision === "ACCEPT"
    ? "Accepted"
    : decision === "DOUBTFUL"
      ? "Doubtful"
      : decision === "REJECT"
        ? "Rejected"
        : "Error";

  return (
    <article className={`candidate-card ${cardClass}`}>
      <div className="candidate-card__header">
        <div>
          <h4 className="candidate-card__name">{result.candidate_name || "Unknown Candidate"}</h4>
          <p className="candidate-card__file">{result.file_name}</p>
        </div>
        <span className={`badge ${badgeClass}`}>{badgeLabel}</span>
      </div>

      {!hasError && score !== null ? (
        <p className="candidate-card__score">Match Score: {Math.round(score)}/100</p>
      ) : null}

      {routingLabel ? <p className="candidate-card__routing">{routingLabel}</p> : null}

      {hasError ? (
        <p className="candidate-card__error">Could not process this resume: {result.error}</p>
      ) : null}
    </article>
  );
}
