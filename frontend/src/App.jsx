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

export default function App() {
  const { toasts, pushToast, dismissToast } = useToasts();
  const { status, jobId, deducedJobs, progress, results, beginScreening, reset } = useScreeningJob(pushToast);
  const [jobSpecFile, setJobSpecFile] = useState(null);

  const accepted = results.filter((r) => r.decision === "ACCEPT" && !r.error);
  const doubtful = results.filter((r) => r.decision === "DOUBTFUL" && !r.error);
  const rejected = results.filter((r) => r.decision === "REJECT" || r.error);
  const failed = results.filter((r) => r.error);
  const jobGroups = Array.from(new Set(results.map((r) => (r.routed_job_titles && r.routed_job_titles[0]) || "General Role"))).filter(Boolean);

  const remaining = Math.max(progress.total - progress.processed, 0);
  const isActive = status === "processing" || status === "uploading";
  const skeletonsPerPanel = isActive ? Math.min(remaining, 3) : 0;

  return (
    <>
      <Navbar />

      <main className="main">
        <div className="container">
          <section className="step-panel">
            <span className="step-panel__eyebrow">Step 1</span>
            <h2 className="step-panel__title">Job specification</h2>
            <RequirementsPanel jobSpecFile={jobSpecFile} setJobSpecFile={setJobSpecFile} status={status} deducedJobs={deducedJobs} />
          </section>

          <section className="step-panel">
            <span className="step-panel__eyebrow">Step 2</span>
            <h2 className="step-panel__title">Candidate resumes</h2>
            <UploadArea onStart={beginScreening} status={status} jobSpecFile={jobSpecFile} setJobSpecFile={setJobSpecFile} />
          </section>

          <section className="step-panel">
            <span className="step-panel__eyebrow">Step 3</span>
            <h2 className="step-panel__title">Screening progress</h2>
            <ProgressPanel status={status} progress={progress} />
          </section>

          <ExportBar jobId={jobId} status={status} onReset={reset} />

          <div className="results-sections">
            {jobGroups.length > 0 ? (
              jobGroups.map((jobTitle) => {
                const jobResults = results.filter((result) => (result.routed_job_titles && result.routed_job_titles[0]) === jobTitle);
                const acceptedForJob = jobResults.filter((r) => r.decision === "ACCEPT" && !r.error);
                const doubtfulForJob = jobResults.filter((r) => r.decision === "DOUBTFUL" && !r.error);
                const rejectedForJob = jobResults.filter((r) => r.decision === "REJECT" || r.error);

                return (
                  <section key={jobTitle} className="results-section">
                    <div className="results-section__header">
                      <h3>{jobTitle || "General Role"}</h3>
                      <p>{jobResults.length} candidate{jobResults.length === 1 ? "" : "s"} routed here</p>
                    </div>
                    <div className="results-grid results-grid--grouped">
                      <ResultsPanel title="Accepted" variant="accept" results={acceptedForJob} pendingCount={skeletonsPerPanel} status={status} />
                      <ResultsPanel title="Doubtful" variant="doubtful" results={doubtfulForJob} pendingCount={skeletonsPerPanel} status={status} />
                      <ResultsPanel title="Rejected" variant="reject" results={rejectedForJob} pendingCount={skeletonsPerPanel} status={status} />
                    </div>
                  </section>
                );
              })
            ) : (
              <div className="results-grid">
                <ResultsPanel title="Accepted" variant="accept" results={accepted} pendingCount={skeletonsPerPanel} status={status} />
                <ResultsPanel title="Doubtful" variant="doubtful" results={doubtful} pendingCount={skeletonsPerPanel} status={status} />
                <ResultsPanel title="Rejected" variant="reject" results={rejected} pendingCount={skeletonsPerPanel} status={status} />
              </div>
            )}
          </div>
        </div>
      </main>

      <Footer />
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
