import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { useProjects } from "../stores/projects";

export default function ProjectsPage() {
  const { t } = useTranslation();
  const { projects, crsCatalog, fetch, create } = useProjects();
  const [name, setName] = useState("");
  const [crsId, setCrsId] = useState<number | "">("");
  const [errorKey, setErrorKey] = useState<string | null>(null);

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

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "1rem" }}>
      <h1>{t("projects.title")}</h1>

      <form onSubmit={submit} style={{ display: "flex", gap: 8, alignItems: "end" }}>
        <label>
          {t("projects.name")}
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
        </label>
        <label>
          {t("projects.crs")}
          <select value={crsId} onChange={(e) => setCrsId(Number(e.target.value))} required>
            <option value="" disabled />
            {crsCatalog.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {t(entry.label_key)} ({entry.code})
              </option>
            ))}
          </select>
        </label>
        <button type="submit">{t("projects.create")}</button>
      </form>
      {errorKey && <p role="alert">{t(errorKey)}</p>}

      {projects.length === 0 ? (
        <p>{t("projects.empty")}</p>
      ) : (
        <ul>
          {projects.map((project) => (
            <li key={project.id}>
              <Link to={`/projects/${project.id}`}>{project.name}</Link>{" "}
              <small>
                {project.crs.code} — {t("projects.surveys_count", { count: project.survey_count })}
              </small>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
