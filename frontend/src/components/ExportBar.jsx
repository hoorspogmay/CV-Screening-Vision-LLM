import { exportCsvUrl } from "../utils/api.js";

export default function ExportBar({ jobId, status, onReset }) {
  if (!jobId || status === "idle") return null;

  return (
    <div className="export-bar">
      <p className="export-bar__hint">
        {status === "completed" ? "Screening finished." : "You can export results once processing has started."}
      </p>
      <div className="export-bar__actions">
        <button type="button" className="btn btn--ghost" onClick={onReset}>
          New Batch
        </button>
        <a className="btn btn--primary" href={exportCsvUrl(jobId)} download>
          Export CSV
        </a>
      </div>
    </div>
  );
}
