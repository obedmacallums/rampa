// Per-stage progress with 4 s polling that stops on terminal states (R8,
// SC-004); failures show the localized cause + corrective action and a retry
// button (US2).
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, SurveyDetail, Stage } from "../api/client";
import Badge from "../ui/Badge";
import Button from "../ui/Button";

const STAGES: Stage[] = ["validation", "reprojection", "surface_generation"];
const POLL_MS = 4000;

interface Props {
  surveyId: string;
  onTerminal?: () => void;
}

export default function SurveyStatus({ surveyId, onTerminal }: Props) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<SurveyDetail | null>(null);

  const refresh = useCallback(async () => {
    const data = await api.getSurvey(surveyId);
    setDetail(data);
    return data;
  }, [surveyId]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;
    const tick = async () => {
      try {
        const data = await refresh();
        if (cancelled) return;
        if (data.status === "queued" || data.status === "processing") {
          timer = setTimeout(tick, POLL_MS);
        } else {
          onTerminal?.();
        }
      } catch {
        timer = setTimeout(tick, POLL_MS);
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [refresh, onTerminal]);

  if (!detail) return null;
  const run = detail.latest_run;

  return (
    <div className="grid justify-items-start gap-1.5">
      <Badge status={detail.status} label={t(`status.${detail.status}`)} />
      {detail.status === "processing" && run && (
        <ol className="flex gap-3 text-xs">
          {STAGES.map((stage) => (
            <li
              key={stage}
              className={
                run.stage === stage ? "font-semibold text-status-processing" : "text-text-muted"
              }
            >
              {t(`stage.${stage}`)}
            </li>
          ))}
        </ol>
      )}
      {detail.status === "failed" && run?.failure_message_key && (
        <div role="alert" className="grid justify-items-start gap-2">
          <p className="text-xs text-status-failed">{t(run.failure_message_key)}</p>
          <Button
            variant="secondary"
            onClick={() => {
              void api.retrySurvey(surveyId).then(refresh);
            }}
          >
            {t("surveys.retry")}
          </Button>
        </div>
      )}
    </div>
  );
}
