import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api, ApiError, ArtifactSet } from "../api/client";
import PendingUploads from "../components/PendingUploads";
import ProjectMembers from "../components/ProjectMembers";
import SurveyStatus from "../components/SurveyStatus";
import UploadWidget from "../components/UploadWidget";
import { useSurveys } from "../stores/surveys";
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
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "1rem" }}>
      <PendingUploads projectId={projectId} />
      <UploadWidget projectId={projectId} onUploadFinished={refresh} />

      <h2>{t("surveys.title")}</h2>
      {surveys.length === 0 ? (
        <p>{t("surveys.empty")}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>{t("surveys.name")}</th>
              <th>{t("surveys.capture_date")}</th>
              <th>{t("surveys.size")}</th>
              <th>{t("surveys.status")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {surveys.map((survey) => (
              <tr key={survey.id}>
                <td>{survey.name}</td>
                <td>{new Date(survey.capture_date).toLocaleDateString(i18n.language)}</td>
                <td>{formatSize(survey.source_size_bytes)}</td>
                <td>
                  <SurveyStatus surveyId={survey.id} onTerminal={refresh} />
                </td>
                <td>
                  {survey.status === "completed" && (
                    <>
                      <button onClick={() => void openViewer(survey.id, "2d")}>
                        {t("surveys.view_2d")}
                      </button>{" "}
                      <button onClick={() => void openViewer(survey.id, "3d")}>
                        {t("surveys.view_3d")}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {viewerError && <p role="alert">{t(viewerError)}</p>}

      <ProjectMembers projectId={projectId} />

      {viewer === "2d" && artifacts && <Map2D tilejsonUrl={artifacts.hillshade.tilejson_url} />}
      {viewer === "3d" && artifacts && (
        <Cloud3D
          copcUrl={artifacts.copc.url}
          onUrlExpired={() => {
            // presigned URL expired mid-session: fetch a fresh ArtifactSet
            const surveyId = surveys.find((s) => s.status === "completed")?.id;
            if (surveyId) void openViewer(surveyId, "3d");
          }}
        />
      )}
    </main>
  );
}
