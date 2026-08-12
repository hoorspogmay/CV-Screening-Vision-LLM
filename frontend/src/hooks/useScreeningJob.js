import { useCallback, useRef, useState } from "react";
import { startScreening, openScreeningSocket } from "../utils/api.js";

const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

function isAllowedFile(file) {
  const name = file.name.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

/**
 * Owns the entire lifecycle of a screening job: uploading files, tracking
 * live progress and results over WebSocket, and exposing state for the UI.
 */
export function useScreeningJob(pushToast) {
  const [status, setStatus] = useState("idle"); // idle | uploading | processing | completed
  const [jobId, setJobId] = useState(null);
  const [deducedJobs, setDeducedJobs] = useState([]);
  const [progress, setProgress] = useState({ total: 0, processed: 0, accepted: 0, doubtful: 0, rejected: 0, failed: 0 });
  const [results, setResults] = useState([]);
  const socketRef = useRef(null);

  const reset = useCallback(() => {
    socketRef.current?.close();
    setStatus("idle");
    setJobId(null);
    setDeducedJobs([]);
    setProgress({ total: 0, processed: 0, accepted: 0, doubtful: 0, rejected: 0, failed: 0 });
    setResults([]);
  }, []);

  const beginScreening = useCallback(
    async (rawFiles, jobSpecFile) => {
      const files = rawFiles.filter(isAllowedFile);
      const skipped = rawFiles.length - files.length;

      if (!jobSpecFile) {
        pushToast("Please upload a Microsoft Word job specification document first.", "error");
        return;
      }
      if (files.length === 0) {
        pushToast("No PDF or DOCX resumes found in your selection.", "error");
        return;
      }
      if (skipped > 0) {
        pushToast(`Skipped ${skipped} unsupported file${skipped > 1 ? "s" : ""}.`, "info");
      }

      setResults([]);
      setStatus("uploading");
      setProgress({ total: files.length, processed: 0, accepted: 0, doubtful: 0, rejected: 0, failed: 0 });

      try {
        const { job_id, total_files, job_profiles } = await startScreening(files, jobSpecFile);
        setJobId(job_id);
        setDeducedJobs(job_profiles || []);
        setProgress((prev) => ({ ...prev, total: total_files }));
        setStatus("processing");

        const socket = openScreeningSocket(job_id);
        socketRef.current = socket;

        let completed = false;
        socket.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.type === "result" && payload.result) {
            setResults((prev) => [payload.result, ...prev]);
          } else if (payload.type === "progress" && payload.progress) {
            setProgress(payload.progress);
          } else if (payload.type === "done") {
            completed = true;
            setStatus("completed");
            pushToast("Screening complete.", "success");
            socket.close();
          } else if (payload.type === "error") {
            pushToast(payload.message || "An error occurred during screening.", "error");
            setStatus("idle");
          }
        };

        socket.onerror = () => {
          if (!completed) {
            pushToast("Lost connection to the screening service.", "error");
          }
        };

        socket.onclose = (event) => {
          if (!completed && event.code !== 1000 && event.code !== 1001) {
            pushToast("The screening connection closed unexpectedly.", "error");
          }
        };
      } catch (err) {
        setStatus("idle");
        pushToast(err.message || "Failed to start screening.", "error");
      }
    },
    [pushToast]
  );

  return { status, jobId, deducedJobs, progress, results, beginScreening, reset };
}
