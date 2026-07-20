// "Process more options" (US3): request additional products on an already
// processed survey, reusing the stored source file — no re-upload, no new
// upload session. Reuses OptionPicker; options already produced on this
// survey render locked (re-requesting them is harmless — the server unions
// and reuses — but locking avoids implying they'd be regenerated).
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, ApiError, ProcessingOption, SurveyDetail } from "../api/client";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import OptionPicker from "./OptionPicker";

interface Props {
  survey: SurveyDetail;
  onClose: () => void;
  onQueued: () => void;
}

function producedOptionIds(survey: SurveyDetail): Set<string> {
  const ids = new Set<string>();
  for (const run of survey.runs) {
    for (const option of run.options) {
      if (option.state === "completed" || option.state === "reused") {
        ids.add(option.option_id);
      }
    }
  }
  return ids;
}

export default function ProcessMoreDialog({ survey, onClose, onQueued }: Props) {
  const { t } = useTranslation();
  const [catalog, setCatalog] = useState<ProcessingOption[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [alreadyProduced, setAlreadyProduced] = useState<Set<string>>(new Set());
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void api.getProcessingOptions(survey.input_type).then((data) => {
      setCatalog(data.options);
      const produced = producedOptionIds(survey);
      setAlreadyProduced(produced);
      setSelected(new Set(produced));
    });
  }, [survey]);

  const submit = async () => {
    setErrorKey(null);
    setSubmitting(true);
    try {
      await api.processSurvey(survey.id, Array.from(selected));
      onQueued();
    } catch (error) {
      setErrorKey(error instanceof ApiError ? error.messageKey : "errors.invalid_request");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid gap-3 rounded-lg border border-surface-2 bg-surface-1 p-4">
      <h3 className="text-sm font-semibold text-text-strong">{t("surveys.process_more")}</h3>
      {catalog.length > 0 && (
        <OptionPicker
          options={catalog}
          selected={selected}
          onChange={setSelected}
          locked={alreadyProduced}
        />
      )}
      {errorKey && <Alert>{t(errorKey)}</Alert>}
      <div className="flex gap-2">
        <Button onClick={() => void submit()} disabled={submitting}>
          {t("surveys.process_more_submit")}
        </Button>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          {t("common.cancel")}
        </Button>
      </div>
    </div>
  );
}
