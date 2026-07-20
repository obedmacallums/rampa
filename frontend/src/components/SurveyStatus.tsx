// Per-option progress with 4 s polling that stops on terminal states (R8,
// SC-004, FR-010): each option in the latest run renders its own state badge
// (pending/running/completed/failed/skipped/reused) — the primary progress
// signal once options start (data-model.md) — plus a translated failure
// message for whichever option actually failed. Failures show a retry button
// (US2); per-option publication means completed options stay visible even
// when the run as a whole ends failed (quickstart Scenario 4).
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, SurveyDetail } from "../api/client";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import ProcessMoreDialog from "./ProcessMoreDialog";

const POLL_MS = 4000;

interface Props {
  surveyId: string;
  onTerminal?: () => void;
}

export default function SurveyStatus({ surveyId, onTerminal }: Props) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<SurveyDetail | null>(null);
  const [showProcessMore, setShowProcessMore] = useState(false);

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
      {run && run.options.length > 0 && (
        <ul className="grid gap-1">
          {run.options.map((opt) => (
            <li key={opt.option_id} className="flex flex-wrap items-center gap-2 text-xs">
              <Badge status={opt.state} label={t(`options.state.${opt.state}`)} />
              <span className="text-text-muted">{t(`options.${opt.option_id}.label`)}</span>
              {opt.state === "failed" && opt.failure_message_key && (
                <span className="text-status-failed">{t(opt.failure_message_key)}</span>
              )}
            </li>
          ))}
        </ul>
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
      {(detail.status === "completed" || detail.status === "failed") && !showProcessMore && (
        <Button variant="secondary" onClick={() => setShowProcessMore(true)}>
          {t("surveys.process_more")}
        </Button>
      )}
      {showProcessMore && (
        <ProcessMoreDialog
          survey={detail}
          onClose={() => setShowProcessMore(false)}
          onQueued={() => {
            setShowProcessMore(false);
            void refresh();
          }}
        />
      )}
    </div>
  );
}
