// Re-offers interrupted uploads (US3). Resumption itself happens in
// UploadWidget: tus fingerprints the file, so selecting it again continues
// from the last confirmed offset instead of restarting. A pending upload
// can also be cancelled outright (mirrors 005's delete/ConfirmDialog flow).
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, PendingUpload } from "../api/client";
import { useUploads } from "../stores/uploads";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import ConfirmDialog from "../ui/ConfirmDialog";
import ProgressBar from "../ui/ProgressBar";

export default function PendingUploads({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const { pendingByProject, fetchPending, cancel } = useUploads();
  const [deleteTarget, setDeleteTarget] = useState<PendingUpload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchPending(projectId);
  }, [projectId, fetchPending]);

  const pending = pendingByProject[projectId] ?? [];

  const confirmCancel = async () => {
    if (!deleteTarget) return;
    try {
      await cancel(projectId, deleteTarget.upload_session_id);
      setDeleteTarget(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.messageKey : "errors.invalid_request");
      setDeleteTarget(null);
    }
  };

  if (pending.length === 0) return null;

  return (
    <section className="grid gap-3 rounded-lg border border-status-warning/40 bg-status-warning/5 p-4">
      <h3 className="text-sm font-semibold text-status-warning">{t("upload.pending_title")}</h3>
      <ul className="grid gap-3">
        {pending.map((upload) => (
          <li key={upload.upload_session_id} className="grid gap-1.5 text-sm">
            <span className="flex items-center gap-2">
              <span className="flex-1 truncate">{upload.declared_filename}</span>
              <Button variant="danger" onClick={() => setDeleteTarget(upload)}>
                {t("upload.delete")}
              </Button>
            </span>
            {upload.received_bytes !== null && (
              <ProgressBar
                percent={Math.round((100 * upload.received_bytes) / upload.declared_size_bytes)}
              />
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-text-muted">{t("upload.pending_hint")}</p>
      {error && <Alert>{t(error)}</Alert>}

      <ConfirmDialog
        open={deleteTarget !== null}
        message={
          deleteTarget
            ? t("upload.delete_confirm", { name: deleteTarget.declared_filename })
            : ""
        }
        confirmLabel={t("upload.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => void confirmCancel()}
        onCancel={() => setDeleteTarget(null)}
      />
    </section>
  );
}
