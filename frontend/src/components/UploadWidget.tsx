// Resumable upload via tus (US1/US3): initiation against the backend, then the
// browser speaks tus directly to tusd. tus-js-client fingerprints the file in
// localStorage, so re-selecting the same file resumes from the last offset —
// including after a browser or machine restart.
import Uppy from "@uppy/core";
import Tus from "@uppy/tus";
import { FormEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";

interface Props {
  projectId: string;
  onUploadFinished: () => void;
}

export default function UploadWidget({ projectId, onUploadFinished }: Props) {
  const { t } = useTranslation();
  const fileInput = useRef<HTMLInputElement>(null);
  const [captureDate, setCaptureDate] = useState("");
  const [surveyName, setSurveyName] = useState("");
  const [percent, setPercent] = useState<number | null>(null);
  const [messageKey, setMessageKey] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    setErrorKey(null);
    setMessageKey(null);

    let initiation;
    try {
      initiation = await api.initiateUpload(projectId, {
        filename: file.name,
        size_bytes: file.size,
        capture_date: captureDate,
        name: surveyName || undefined,
      });
    } catch (error) {
      setErrorKey(error instanceof ApiError ? error.messageKey : "errors.invalid_request");
      return;
    }

    const uppy = new Uppy({ autoProceed: true });
    uppy.use(Tus, {
      endpoint: initiation.tus_endpoint,
      chunkSize: 50 * 1024 * 1024,
      removeFingerprintOnSuccess: true,
    });
    uppy.on("upload-progress", (_file, progress) => {
      if (progress.bytesTotal) {
        setPercent(Math.round((100 * progress.bytesUploaded) / progress.bytesTotal));
      }
    });
    uppy.on("complete", () => {
      setPercent(null);
      setMessageKey("upload.done");
      onUploadFinished();
    });
    uppy.on("error", () => {
      setPercent(null);
      setMessageKey("upload.interrupted");
    });
    uppy.addFile({
      name: file.name,
      data: file,
      meta: { ...initiation.tus_metadata },
    });
  };

  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 8, maxWidth: 480 }}>
      <h2>{t("upload.title")}</h2>
      <label>
        {t("upload.file")}
        <input ref={fileInput} type="file" accept=".las,.laz" required />
      </label>
      <label>
        {t("upload.capture_date")}
        <input
          type="date"
          value={captureDate}
          onChange={(e) => setCaptureDate(e.target.value)}
          required
        />
      </label>
      <label>
        {t("upload.survey_name")}
        <input value={surveyName} onChange={(e) => setSurveyName(e.target.value)} maxLength={120} />
      </label>
      <button type="submit" disabled={percent !== null}>
        {t("upload.start")}
      </button>
      {percent !== null && <progress value={percent} max={100} />}
      {percent !== null && <span>{t("upload.progress", { percent })}</span>}
      {messageKey && <p>{t(messageKey)}</p>}
      {errorKey && <p role="alert">{t(errorKey)}</p>}
    </form>
  );
}
