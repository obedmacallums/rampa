// Re-offers interrupted uploads (US3). Resumption itself happens in
// UploadWidget: tus fingerprints the file, so selecting it again continues
// from the last confirmed offset instead of restarting.
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { useUploads } from "../stores/uploads";

export default function PendingUploads({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const { pendingByProject, fetchPending } = useUploads();

  useEffect(() => {
    void fetchPending(projectId);
  }, [projectId, fetchPending]);

  const pending = pendingByProject[projectId] ?? [];
  if (pending.length === 0) return null;

  return (
    <section>
      <h3>{t("upload.pending_title")}</h3>
      <ul>
        {pending.map((upload) => (
          <li key={upload.upload_session_id}>
            {upload.declared_filename}{" "}
            {upload.received_bytes !== null && (
              <progress value={upload.received_bytes} max={upload.declared_size_bytes} />
            )}
          </li>
        ))}
      </ul>
      <p>
        <small>{t("upload.pending_hint")}</small>
      </p>
    </section>
  );
}
