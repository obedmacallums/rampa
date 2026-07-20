// Re-offers interrupted uploads (US3). Resumption itself happens in
// UploadWidget: tus fingerprints the file, so selecting it again continues
// from the last confirmed offset instead of restarting.
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { useUploads } from "../stores/uploads";
import ProgressBar from "../ui/ProgressBar";

export default function PendingUploads({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const { pendingByProject, fetchPending } = useUploads();

  useEffect(() => {
    void fetchPending(projectId);
  }, [projectId, fetchPending]);

  const pending = pendingByProject[projectId] ?? [];
  if (pending.length === 0) return null;

  return (
    <section className="grid gap-3 rounded-lg border border-status-warning/40 bg-status-warning/5 p-4">
      <h3 className="text-sm font-semibold text-status-warning">{t("upload.pending_title")}</h3>
      <ul className="grid gap-3">
        {pending.map((upload) => (
          <li key={upload.upload_session_id} className="grid gap-1.5 text-sm">
            <span className="truncate">{upload.declared_filename}</span>
            {upload.received_bytes !== null && (
              <ProgressBar
                percent={Math.round((100 * upload.received_bytes) / upload.declared_size_bytes)}
              />
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-text-muted">{t("upload.pending_hint")}</p>
    </section>
  );
}
