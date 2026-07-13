export default function ProgressPanel({ status, progress }) {
  if (status === "idle") return null;

  const { total, processed } = progress;
  const percent = total > 0 ? Math.round((processed / total) * 100) : 0;
  const isProcessing = status === "processing" || status === "uploading";

  return (
    <section className="progress-card" aria-label="Screening progress">
      <div className="progress-card__header">
        <h3>{status === "completed" ? "Screening complete" : "Screening resumes…"}</h3>
        <span className="progress-card__percent">{percent}%</span>
      </div>

      <div className="progress-bar" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div className="progress-bar__track">
          <div className="progress-bar__fill" style={{ width: `${percent}%` }}>
            {isProcessing && <span className="progress-bar__scan" />}
          </div>
        </div>
      </div>

      <div className="progress-stats">
        <div className="progress-stat">
          <span className="progress-stat__value">{total}</span>
          <span className="progress-stat__label">Total Files</span>
        </div>
        <div className="progress-stat">
          <span className="progress-stat__value">{processed}</span>
          <span className="progress-stat__label">Processed</span>
        </div>
        <div className="progress-stat">
          <span className="progress-stat__value">{Math.max(total - processed, 0)}</span>
          <span className="progress-stat__label">Remaining</span>
        </div>
      </div>
    </section>
  );
}
