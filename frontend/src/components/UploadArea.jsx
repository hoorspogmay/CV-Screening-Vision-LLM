import { useCallback, useRef, useState } from "react";

export default function UploadArea({ onStart, status, requirements }) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);

  const isBusy = status === "uploading" || status === "processing";

  const addFiles = useCallback((fileList) => {
    setSelectedFiles((prev) => [...prev, ...Array.from(fileList)]);
  }, []);

  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      setIsDragging(false);
      if (isBusy) return;
      if (event.dataTransfer.files?.length) {
        addFiles(event.dataTransfer.files);
      }
    },
    [addFiles, isBusy]
  );

  const clearSelection = () => setSelectedFiles([]);

  const handleStart = () => {
    if (selectedFiles.length === 0) return;
    onStart(selectedFiles, requirements);
  };

  return (
    <section className="upload-card" aria-label="Upload resumes">
      <div
        className={`dropzone ${isDragging ? "dropzone--active" : ""} ${isBusy ? "dropzone--disabled" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!isBusy) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <div className="dropzone__icon" aria-hidden="true">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
            <rect x="4" y="4" width="32" height="32" rx="10" fill="var(--color-primary-tint)" />
            <path
              d="M20 26V14M20 14l-5 5M20 14l5 5"
              stroke="var(--color-primary)"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path d="M13 27h14" stroke="var(--color-primary)" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
        </div>

        <h3 className="dropzone__title">Drag and drop resumes here</h3>
        <p className="dropzone__subtitle">PDF and DOCX files, or an entire folder of resumes</p>

        <div className="dropzone__actions">
          <button
            type="button"
            className="btn btn--secondary"
            disabled={isBusy}
            onClick={() => fileInputRef.current?.click()}
          >
            Upload Files
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            disabled={isBusy}
            onClick={() => folderInputRef.current?.click()}
          >
            Upload Folder
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx"
          hidden
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
        <input
          ref={folderInputRef}
          type="file"
          multiple
          webkitdirectory=""
          directory=""
          hidden
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {selectedFiles.length > 0 && (
        <div className="selection-bar">
          <span className="selection-bar__count">
            {selectedFiles.length} resume{selectedFiles.length > 1 ? "s" : ""} selected
          </span>
          <div className="selection-bar__actions">
            <button type="button" className="btn btn--ghost" disabled={isBusy} onClick={clearSelection}>
              Clear
            </button>
            <button type="button" className="btn btn--primary" disabled={isBusy} onClick={handleStart}>
              {isBusy ? "Screening in progress…" : "Start Screening"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
