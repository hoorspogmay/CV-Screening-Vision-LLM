import "./styles/app.css";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import UploadArea from "./components/UploadArea.jsx";
import ProgressPanel from "./components/ProgressPanel.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";
import ExportBar from "./components/ExportBar.jsx";
import ToastContainer from "./components/ToastContainer.jsx";
import { useScreeningJob } from "./hooks/useScreeningJob.js";
import { useToasts } from "./hooks/useToasts.js";

export default function App() {
  const { toasts, pushToast, dismissToast } = useToasts();
  const { status, jobId, progress, results, beginScreening, reset } = useScreeningJob(pushToast);

  const accepted = results.filter((r) => r.decision === "ACCEPT" && !r.error);
  const rejected = results.filter((r) => r.decision !== "ACCEPT" || r.error);

  const remaining = Math.max(progress.total - progress.processed, 0);
  const isActive = status === "processing" || status === "uploading";
  const skeletonsPerPanel = isActive ? Math.min(remaining, 3) : 0;

  return (
    <>
      <Navbar />

      <main className="main">
        <div className="container">
          <UploadArea onStart={beginScreening} status={status} />

          <ProgressPanel status={status} progress={progress} />

          <ExportBar jobId={jobId} status={status} onReset={reset} />

          <div className="results-grid">
            <ResultsPanel
              title="Accepted Candidates"
              variant="accept"
              results={accepted}
              pendingCount={skeletonsPerPanel}
              status={status}
            />
            <ResultsPanel
              title="Rejected Candidates"
              variant="reject"
              results={rejected}
              pendingCount={skeletonsPerPanel}
              status={status}
            />
          </div>
        </div>
      </main>

      <Footer />
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
