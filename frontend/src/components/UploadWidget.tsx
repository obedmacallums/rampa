// Resumable upload via tus (US1/US3): initiation against the backend, then the
// browser speaks tus directly to tusd. tus-js-client fingerprints the file in
// localStorage, so re-selecting the same file resumes from the last offset —
// including after a browser or machine restart.
import Uppy from "@uppy/core";
import Tus from "@uppy/tus";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, ApiError, ProcessingOption } from "../api/client";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import Field from "../ui/Field";
import ProgressBar from "../ui/ProgressBar";
import OptionPicker from "./OptionPicker";

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
  const [catalog, setCatalog] = useState<ProcessingOption[]>([]);
  const [selectedOptions, setSelectedOptions] = useState<Set<string>>(new Set());

  useEffect(() => {
    void api.getProcessingOptions().then((data) => {
      setCatalog(data.options);
      setSelectedOptions(
        new Set(
          data.options.filter((option) => option.required || option.default_selected).map((option) => option.id),
        ),
      );
    });
  }, []);

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
        selected_options: Array.from(selectedOptions),
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
    <form
      onSubmit={submit}
      className="grid max-w-lg gap-4 rounded-lg border border-surface-2 bg-surface-1 p-4"
    >
      <h2 className="text-lg font-semibold text-text-strong">{t("upload.title")}</h2>
      <Field label={t("upload.file")}>
        <input ref={fileInput} type="file" accept=".las,.laz" required />
      </Field>
      <Field label={t("upload.capture_date")}>
        <input
          type="date"
          value={captureDate}
          onChange={(e) => setCaptureDate(e.target.value)}
          required
        />
      </Field>
      <Field label={t("upload.survey_name")}>
        <input value={surveyName} onChange={(e) => setSurveyName(e.target.value)} maxLength={120} />
      </Field>
      {catalog.length > 0 && (
        <OptionPicker options={catalog} selected={selectedOptions} onChange={setSelectedOptions} />
      )}
      <Button type="submit" disabled={percent !== null}>
        {t("upload.start")}
      </Button>
      {percent !== null && (
        <div className="grid gap-1.5">
          <ProgressBar percent={percent} />
          <span className="text-xs text-text-muted">{t("upload.progress", { percent })}</span>
        </div>
      )}
      {messageKey && <Alert kind="info">{t(messageKey)}</Alert>}
      {errorKey && <Alert>{t(errorKey)}</Alert>}
    </form>
  );
}
