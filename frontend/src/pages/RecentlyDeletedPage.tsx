import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, ApiError, DeletedItems } from "../api/client";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import EmptyState from "../ui/EmptyState";
import { Table, Td, Th } from "../ui/Table";

const MS_PER_DAY = 24 * 60 * 60 * 1000;

function daysUntil(iso: string): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / MS_PER_DAY));
}

// US3: global restore view (owner-scoped) — deleted projects and
// independently-deleted surveys, each restorable within its recovery window
// (quickstart Scenarios 4-6).
export default function RecentlyDeletedPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<DeletedItems | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .listDeleted()
      .then(setItems)
      .catch((err) => {
        setError(err instanceof ApiError ? err.messageKey : "errors.invalid_request");
      });
  }, []);

  useEffect(refresh, [refresh]);

  const restoreProject = async (id: string) => {
    try {
      await api.restoreProject(id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.messageKey : "errors.invalid_request");
    }
  };

  const restoreSurvey = async (id: string) => {
    try {
      await api.restoreSurvey(id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.messageKey : "errors.invalid_request");
    }
  };

  if (!items) return null;
  const empty = items.projects.length === 0 && items.surveys.length === 0;

  return (
    <main className="mx-auto grid max-w-5xl gap-8 px-6 py-8">
      <h1 className="text-2xl font-semibold tracking-tight text-text-strong">
        {t("deleted.title")}
      </h1>
      {error && <Alert>{t(error)}</Alert>}

      {empty ? (
        <EmptyState message={t("deleted.empty")} />
      ) : (
        <>
          {items.projects.length > 0 && (
            <section className="grid gap-3">
              <h2 className="text-lg font-semibold text-text-strong">
                {t("deleted.projects_heading")}
              </h2>
              <Table>
                <thead>
                  <tr>
                    <Th>{t("projects.name")}</Th>
                    <Th />
                    <Th />
                  </tr>
                </thead>
                <tbody>
                  {items.projects.map((project) => (
                    <tr key={project.id}>
                      <Td>
                        <span className="font-medium text-text-strong">{project.name}</span>
                      </Td>
                      <Td>{t("deleted.expires_in", { days: daysUntil(project.purge_at) })}</Td>
                      <Td>
                        <Button variant="secondary" onClick={() => void restoreProject(project.id)}>
                          {t("deleted.restore")}
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </section>
          )}

          {items.surveys.length > 0 && (
            <section className="grid gap-3">
              <h2 className="text-lg font-semibold text-text-strong">
                {t("deleted.surveys_heading")}
              </h2>
              <Table>
                <thead>
                  <tr>
                    <Th>{t("surveys.name")}</Th>
                    <Th>{t("projects.title")}</Th>
                    <Th />
                    <Th />
                  </tr>
                </thead>
                <tbody>
                  {items.surveys.map((survey) => (
                    <tr key={survey.id}>
                      <Td>
                        <span className="font-medium text-text-strong">{survey.name}</span>
                      </Td>
                      <Td>{survey.project.name}</Td>
                      <Td>{t("deleted.expires_in", { days: daysUntil(survey.purge_at) })}</Td>
                      <Td>
                        <Button variant="secondary" onClick={() => void restoreSurvey(survey.id)}>
                          {t("deleted.restore")}
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </section>
          )}
        </>
      )}
    </main>
  );
}
