import { FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api, ApiError, ProjectSummary } from "../api/client";
import { useProjects } from "../stores/projects";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import ConfirmDialog from "../ui/ConfirmDialog";
import EmptyState from "../ui/EmptyState";
import Field from "../ui/Field";

export default function ProjectsPage() {
  const { t } = useTranslation();
  const { projects, crsCatalog, fetch, create } = useProjects();
  const nameInput = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [crsId, setCrsId] = useState<number | "">("");
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (crsId === "") return;
    setErrorKey(null);
    try {
      await create(name, crsId);
      setName("");
    } catch (error) {
      setErrorKey(error instanceof ApiError ? error.messageKey : "errors.invalid_request");
    }
  };

  const confirmDeleteProject = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteProject(deleteTarget.id);
      setDeleteTarget(null);
      await fetch();
    } catch (error) {
      setDeleteError(error instanceof ApiError ? error.messageKey : "errors.invalid_request");
      setDeleteTarget(null);
    }
  };

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-text-strong">
          {t("projects.title")}
        </h1>
        <Link to="/deleted" className="text-sm text-text-muted transition-colors hover:text-text-strong">
          {t("nav.deleted")}
        </Link>
      </div>

      <form
        onSubmit={submit}
        className="mt-6 flex flex-wrap items-end gap-4 rounded-lg border border-surface-2 bg-surface-1 p-4"
      >
        <Field label={t("projects.name")}>
          <input
            ref={nameInput}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={120}
          />
        </Field>
        <Field label={t("projects.crs")}>
          <select value={crsId} onChange={(e) => setCrsId(Number(e.target.value))} required>
            <option value="" disabled />
            {crsCatalog.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {t(entry.label_key)} ({entry.code})
              </option>
            ))}
          </select>
        </Field>
        <Button type="submit">{t("projects.create")}</Button>
      </form>
      {errorKey && (
        <div className="mt-3">
          <Alert>{t(errorKey)}</Alert>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="mt-8">
          <EmptyState
            message={t("projects.empty")}
            action={
              <Button variant="secondary" onClick={() => nameInput.current?.focus()}>
                {t("projects.create")}
              </Button>
            }
          />
        </div>
      ) : (
        <ul className="mt-8 grid gap-3">
          {projects.map((project) => (
            <li
              key={project.id}
              className="flex items-center gap-3 rounded-lg border border-surface-2 bg-surface-1 px-4 py-3 transition-colors hover:border-accent/60"
            >
              <Link to={`/projects/${project.id}`} className="flex-1">
                <span className="font-medium text-text-strong">{project.name}</span>
                <span className="mt-1 block text-xs text-text-muted">
                  {project.crs.code} —{" "}
                  {t("projects.surveys_count", { count: project.survey_count })}
                </span>
              </Link>
              {project.is_owner && (
                <Button variant="danger" onClick={() => setDeleteTarget(project)}>
                  {t("projects.delete")}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {deleteError && (
        <div className="mt-3">
          <Alert>{t(deleteError)}</Alert>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        message={deleteTarget ? t("projects.delete_confirm", { name: deleteTarget.name }) : ""}
        confirmLabel={t("projects.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => void confirmDeleteProject()}
        onCancel={() => setDeleteTarget(null)}
      />
    </main>
  );
}
