export default function CandidateCard({ result }) {
  const isAccepted = result.decision === "ACCEPT";
  const hasError = Boolean(result.error);

  return (
    <article className={`candidate-card ${isAccepted ? "candidate-card--accept" : "candidate-card--reject"}`}>
      <div className="candidate-card__header">
        <div>
          <h4 className="candidate-card__name">{result.candidate_name || "Unknown Candidate"}</h4>
          <p className="candidate-card__file">{result.file_name}</p>
        </div>
        <span className={`badge ${isAccepted ? "badge--accept" : "badge--reject"}`}>
          {isAccepted ? "Accepted" : "Rejected"}
        </span>
      </div>

      {hasError ? (
        <p className="candidate-card__error">Could not process this resume: {result.error}</p>
      ) : null}
    </article>
  );
}
