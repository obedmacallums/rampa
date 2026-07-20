import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api, ApiError, ProductArtifact, SurveySummary } from "../api/client";
import PendingUploads from "../components/PendingUploads";
import ProjectMembers from "../components/ProjectMembers";
import SurveyStatus from "../components/SurveyStatus";
import UploadWidget from "../components/UploadWidget";
import { useProjects } from "../stores/projects";
import { useSurveys } from "../stores/surveys";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import ConfirmDialog from "../ui/ConfirmDialog";
import EmptyState from "../ui/EmptyState";
import { Table, Td, Th } from "../ui/Table";
import ViewerModeSwitch from "../ui/ViewerModeSwitch";
import ViewerOverlay from "../ui/ViewerOverlay";
import Cloud3D from "../viewers/Cloud3D";
import Map2D from "../viewers/Map2D";

function formatSize(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export default function ProjectDetailPage() {
  const { t, i18n } = useTranslation();
  const { projectId } = useParams<{ projectId: string }>();
  const { byProject, fetch } = useSurveys();
  const { projects, fetch: fetchProjects } = useProjects();
  const [products, setProducts] = useState<Record<string, ProductArtifact> | null>(null);
  const [viewer, setViewer] = useState<"2d" | "3d" | null>(null);
  const [viewerSurveyId, setViewerSurveyId] = useState<string | null>(null);
  const [viewerTitle, setViewerTitle] = useState("");
  const [viewerError, setViewerError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SurveySummary | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (projectId) void fetch(projectId);
  }, [projectId, fetch]);

  useEffect(refresh, [refresh]);
  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  if (!projectId) return null;
  const surveys = byProject[projectId] ?? [];
  const isOwner = projects.find((p) => p.id === projectId)?.is_owner ?? false;

  const confirmDeleteSurvey = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteSurvey(deleteTarget.id);
      setDeleteTarget(null);
      refresh();
    } catch (error) {
      setDeleteError(error instanceof ApiError ? error.messageKey : "errors.invalid_request");
      setDeleteTarget(null);
    }
  };

  // Which product resolved decides both what's viewable and which mode opens
  // by default (FR-005/FR-016) — a survey can have partial products even
  // when its overall status is "failed" (per-option publication, FR-009).
  const openViewer = async (surveyId: string, kind: "2d" | "3d") => {
    setViewerError(null);
    try {
      const { products: resolved } = await api.getArtifacts(surveyId);
      setProducts(resolved);
      setViewerSurveyId(surveyId);
      setViewerTitle(surveys.find((s) => s.id === surveyId)?.name ?? "");
      const has2d = Boolean(resolved.elevation);
      const has3d = Boolean(resolved.point_cloud_3d);
      setViewer(kind === "3d" && has3d ? "3d" : has2d ? "2d" : has3d ? "3d" : null);
    } catch (error) {
      setViewerError(
        error instanceof ApiError && error.code === "not_ready"
          ? "viewer.not_ready"
          : "errors.invalid_request",
      );
    }
  };

  return (
    <main className="mx-auto grid max-w-5xl gap-8 px-6 py-8">
      <PendingUploads projectId={projectId} />
      <UploadWidget projectId={projectId} onUploadFinished={refresh} />

      <section className="grid gap-4">
        <h2 className="text-lg font-semibold text-text-strong">{t("surveys.title")}</h2>
        {surveys.length === 0 ? (
          <EmptyState message={t("surveys.empty")} />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>{t("surveys.name")}</Th>
                <Th>{t("surveys.capture_date")}</Th>
                <Th>{t("surveys.size")}</Th>
                <Th>{t("surveys.status")}</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {surveys.map((survey) => (
                <tr key={survey.id} className="transition-colors hover:bg-surface-1/60">
                  <Td>
                    <span className="font-medium text-text-strong">{survey.name}</span>
                  </Td>
                  <Td>{new Date(survey.capture_date).toLocaleDateString(i18n.language)}</Td>
                  <Td>{formatSize(survey.source_size_bytes)}</Td>
                  <Td>
                    <SurveyStatus surveyId={survey.id} onTerminal={refresh} />
                  </Td>
                  <Td>
                    <span className="flex gap-2">
                      {(survey.status === "completed" || survey.status === "failed") && (
                        <Button
                          variant="secondary"
                          onClick={() => void openViewer(survey.id, "2d")}
                        >
                          {t("surveys.view")}
                        </Button>
                      )}
                      {isOwner && (
                        <Button variant="danger" onClick={() => setDeleteTarget(survey)}>
                          {t("surveys.delete")}
                        </Button>
                      )}
                    </span>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </section>
      {viewerError && <Alert>{t(viewerError)}</Alert>}
      {deleteError && <Alert>{t(deleteError)}</Alert>}

      <ConfirmDialog
        open={deleteTarget !== null}
        message={deleteTarget ? t("surveys.delete_confirm", { name: deleteTarget.name }) : ""}
        confirmLabel={t("surveys.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => void confirmDeleteSurvey()}
        onCancel={() => setDeleteTarget(null)}
      />

      <ProjectMembers projectId={projectId} />

      {viewer && products && (
        <ViewerOverlay
          title={viewerTitle}
          onClose={() => setViewer(null)}
          actions={
            <ViewerModeSwitch
              mode={viewer}
              onChange={setViewer}
              show2d={Boolean(products.elevation)}
              show3d={Boolean(products.point_cloud_3d)}
            />
          }
        >
          {viewer === "2d" ? (
            <Map2D
              hillshadeTilejsonUrl={products.hillshade?.tilejson_url}
              demTilejsonUrl={products.elevation.tilejson_url!}
              demStatisticsUrl={products.elevation.statistics_url!}
            />
          ) : (
            <Cloud3D
              copcUrl={products.point_cloud_3d!.url!}
              onUrlExpired={() => {
                // presigned URL expired mid-session: fetch a fresh product set
                if (viewerSurveyId) void openViewer(viewerSurveyId, "3d");
              }}
            />
          )}
        </ViewerOverlay>
      )}
    </main>
  );
}
