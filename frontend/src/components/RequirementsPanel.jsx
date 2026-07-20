import { useState } from "react";

export default function RequirementsPanel({ requirements, setRequirements, status }) {
  const [skillInput, setSkillInput] = useState("");

  const isBusy = status === "uploading" || status === "processing";

  const addSkill = () => {
    const trimmed = skillInput.trim();
    if (!trimmed) return;
    setRequirements((prev) => ({ ...prev, required_skills: Array.from(new Set([...prev.required_skills, trimmed])) }));
    setSkillInput("");
  };

  const removeSkill = (skill) => {
    setRequirements((prev) => ({ ...prev, required_skills: prev.required_skills.filter((item) => item !== skill) }));
  };

  return (
    <section className="upload-card" aria-label="Recruitment requirements">
      <div className="requirements-panel">
        <div className="requirements-panel__header">
          <div>
            <h3 className="dropzone__title">Recruitment Requirements</h3>
            <p className="dropzone__subtitle">Define the role criteria so each resume is screened against them.</p>
          </div>
        </div>

        <div className="requirements-grid">
          <label className="field">
            <span className="field__label">Job Role</span>
            <input
              className="field__input"
              value={requirements.job_role}
              onChange={(event) => setRequirements((prev) => ({ ...prev, job_role: event.target.value }))}
              placeholder="e.g. Healthcare Specialist"
              disabled={isBusy}
            />
          </label>

          <label className="field">
            <span className="field__label">Required Education</span>
            <input
              className="field__input"
              value={requirements.required_education}
              onChange={(event) => setRequirements((prev) => ({ ...prev, required_education: event.target.value }))}
              placeholder="e.g. Bachelor's"
              disabled={isBusy}
            />
          </label>

          <label className="field">
            <span className="field__label">Minimum Experience</span>
            <input
              className="field__input"
              type="number"
              min="0"
              value={requirements.min_experience}
              onChange={(event) => setRequirements((prev) => ({ ...prev, min_experience: event.target.value }))}
              placeholder="2"
              disabled={isBusy}
            />
          </label>

          <label className="field">
            <span className="field__label">Maximum Experience</span>
            <input
              className="field__input"
              type="number"
              min="0"
              value={requirements.max_experience}
              onChange={(event) => setRequirements((prev) => ({ ...prev, max_experience: event.target.value }))}
              placeholder="5"
              disabled={isBusy}
            />
          </label>

          <label className="field">
            <span className="field__label">Accept Threshold</span>
            <input
              className="field__input"
              type="number"
              min="0"
              max="100"
              value={requirements.accept_threshold}
              onChange={(event) => setRequirements((prev) => ({ ...prev, accept_threshold: event.target.value }))}
              placeholder="80"
              disabled={isBusy}
            />
          </label>

          <label className="field">
            <span className="field__label">Doubtful Threshold</span>
            <input
              className="field__input"
              type="number"
              min="0"
              max="100"
              value={requirements.doubtful_threshold}
              onChange={(event) => setRequirements((prev) => ({ ...prev, doubtful_threshold: event.target.value }))}
              placeholder="50"
              disabled={isBusy}
            />
          </label>
        </div>

        <div className="field">
          <span className="field__label">Required Skills</span>
          <div className="skill-input-row">
            <input
              className="field__input"
              value={skillInput}
              onChange={(event) => setSkillInput(event.target.value)}
              placeholder="Add a skill"
              disabled={isBusy}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addSkill();
                }
              }}
            />
            <button type="button" className="btn btn--secondary" disabled={isBusy} onClick={addSkill}>
              Add
            </button>
          </div>
          <div className="skill-list">
            {requirements.required_skills.map((skill) => (
              <span key={skill} className="skill-pill">
                {skill}
                <button type="button" className="skill-pill__remove" aria-label={`Remove ${skill}`} onClick={() => removeSkill(skill)}>
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={requirements.allow_overqualified}
            onChange={(event) => setRequirements((prev) => ({ ...prev, allow_overqualified: event.target.checked }))}
            disabled={isBusy}
          />
          <span>Allow overqualified education matches</span>
        </label>
      </div>
    </section>
  );
}
