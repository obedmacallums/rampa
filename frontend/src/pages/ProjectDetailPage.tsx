import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api, ApiError, ArtifactSet } from "../api/client";
import PendingUploads from "../components/PendingUploads";
import ProjectMembers from "../components/ProjectMembers";
import SurveyStatus from "../components/SurveyStatus";
import UploadWidget from "../components/UploadWidget";
import { useSurveys } from "../stores/surveys";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
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
  const [artifacts, setArtifacts] = useState<ArtifactSet | null>(null);
  const [viewer, setViewer] = useState<"2d" | "3d" | null>(null);
  const [viewerTitle, setViewerTitle] = useState("");
  const [viewerError, setViewerError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (projectId) void fetch(projectId);
  }, [projectId, fetch]);

  useEffect(refresh, [refresh]);

  if (!projectId) return null;
  const surveys = byProject[projectId] ?? [];

  const openViewer = async (surveyId: string, kind: "2d" | "3d") => {
    setViewerError(null);
    try {
      const set = await api.getArtifacts(surveyId);
      setArtifacts(set);
      setViewerTitle(surveys.find((s) => s.id === surveyId)?.name ?? "");
      setViewer(kind);
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
                    {survey.status === "completed" && (
                      <Button variant="secondary" onClick={() => void openViewer(survey.id, "2d")}>
                        {t("surveys.view")}
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </section>
      {viewerError && <Alert>{t(viewerError)}</Alert>}

      <ProjectMembers projectId={projectId} />

      {viewer && artifacts && (
        <ViewerOverlay
          title={viewerTitle}
          onClose={() => setViewer(null)}
          actions={<ViewerModeSwitch mode={viewer} onChange={setViewer} />}
        >
          {viewer === "2d" ? (
            <Map2D
              tilejsonUrl={artifacts.hillshade.tilejson_url}
              demTilejsonUrl={artifacts.dem.tilejson_url}
              demStatisticsUrl={artifacts.dem.statistics_url}
            />
          ) : (
            <Cloud3D
              copcUrl={artifacts.copc.url}
              onUrlExpired={() => {
                // presigned URL expired mid-session: fetch a fresh ArtifactSet
                const surveyId = surveys.find((s) => s.status === "completed")?.id;
                if (surveyId) void openViewer(surveyId, "3d");
              }}
            />
          )}
        </ViewerOverlay>
      )}
    </main>
  );
}
