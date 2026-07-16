const API_BASE = "/api/screening";

/**
 * Uploads all selected files and starts a screening job.
 * Returns { job_id, total_files }.
 */
export async function startScreening(files, requirements) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file, file.webkitRelativePath || file.name));
  if (requirements) {
    formData.append("requirements", JSON.stringify(requirements));
  }

  const response = await fetch(`${API_BASE}/start`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to start screening.");
  }

  return response.json();
}

/** Opens a WebSocket connection for live updates on a job. */
export function openScreeningSocket(jobId) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return new WebSocket(`${protocol}//${host}${API_BASE}/ws/${jobId}`);
}

/** Returns the direct download URL for a job's CSV export. */
export function exportCsvUrl(jobId) {
  return `${API_BASE}/export/${jobId}`;
}

