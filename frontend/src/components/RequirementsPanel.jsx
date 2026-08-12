import { useRef } from "react";

export default function RequirementsPanel({ jobSpecFile, setJobSpecFile, status, deducedJobs }) {
  const inputRef = useRef(null);
  const isBusy = status === "uploading" || status === "processing";

  const handleFileChange = (event) => {
    const file = event.target.files?.[0] || null;
    setJobSpecFile(file);
  };

  return (
    <section className="upload-card" aria-label="Job specification document">
      <div className="requirements-panel">
        <div className="requirements-panel__header">
          <div>
            <h3 className="dropzone__title">Job Specification Document</h3>
            <p className="dropzone__subtitle">Upload a Microsoft Word file containing the role, education, experience, and skill requirements.</p>
          </div>
        </div>

        <div className="field">
          <span className="field__label">Microsoft Word file</span>
          <div className="skill-input-row">
            <input ref={inputRef} type="file" accept=".docx" hidden onChange={handleFileChange} />
            <button type="button" className="btn btn--secondary" disabled={isBusy} onClick={() => inputRef.current?.click()}>
              {jobSpecFile ? "Change File" : "Choose .docx file"}
            </button>
          </div>
          {jobSpecFile ? <p className="dropzone__subtitle">Selected: {jobSpecFile.name}</p> : <p className="dropzone__subtitle">No job specification selected yet.</p>}
        </div>
        {deducedJobs?.length > 0 && (
          <div className="requirements-panel__deduced-jobs">
            <h4>Deduced job openings</h4>
            <ul>
              {deducedJobs.map((job, index) => (
                <li key={`${job.title}-${index}`}>
                  <strong>{job.title || job.requirements?.job_role || "General Role"}</strong>
                  {job.requirements?.required_skills?.length ? ` — ${job.requirements.required_skills.join(", ")}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
