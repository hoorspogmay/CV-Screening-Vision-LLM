import { useState } from "react";
import "./styles/app.css";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import UploadArea from "./components/UploadArea.jsx";
import ProgressPanel from "./components/ProgressPanel.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";
import ExportBar from "./components/ExportBar.jsx";
import ToastContainer from "./components/ToastContainer.jsx";
import RequirementsPanel from "./components/RequirementsPanel.jsx";
import { useScreeningJob } from "./hooks/useScreeningJob.js";
import { useToasts } from "./hooks/useToasts.js";

const emptyRequirements = {
  job_role: "",
  required_education: "",
  min_experience: "",
  max_experience: "",
  accept_threshold: 80,
  doubtful_threshold: 50,
  required_skills: [],
  allow_overqualified: false,
};

export default function App() {
  const { toasts, pushToast, dismissToast } = useToasts();
  const { status, jobId, progress, results, beginScreening, reset } = useScreeningJob(pushToast);
  const [requirements, setRequirements] = useState(emptyRequirements);

  const accepted = results.filter((r) => r.decision === "ACCEPT" && !r.error);
  const doubtful = results.filter((r) => r.decision === "DOUBTFUL" && !r.error);
  const rejected = results.filter((r) => r.decision === "REJECT" || r.error);
  const failed = results.filter((r) => r.error);

  const remaining = Math.max(progress.total - progress.processed, 0);
  const isActive = status === "processing" || status === "uploading";
  const skeletonsPerPanel = isActive ? Math.min(remaining, 3) : 0;

  return (
    <>
      <Navbar />

      <main className="main">
        <div className="container">
          <RequirementsPanel requirements={requirements} setRequirements={setRequirements} status={status} />
          <UploadArea onStart={beginScreening} status={status} requirements={requirements} />

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
              title="Doubtful Candidates"
              variant="doubtful"
              results={doubtful}
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
