// T015: survey delete action is owner-only and gated by the confirm dialog
// (005 US1, mirrors ProjectMembers' remove-member confirm flow).
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

// ProjectDetailPage pulls in Map2D -> maplibre-gl, which calls
// window.URL.createObjectURL at import time (unavailable in jsdom).
vi.mock("maplibre-gl", () => ({ default: {} }));

import "../src/i18n";
import { api, ProjectSummary, SurveyDetail, SurveySummary } from "../src/api/client";
import ProjectDetailPage from "../src/pages/ProjectDetailPage";
import { useProjects } from "../src/stores/projects";
import { useSurveys } from "../src/stores/surveys";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  useSurveys.setState({ byProject: {} });
  useProjects.setState({ projects: [], crsCatalog: [] });
});

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function project(isOwner: boolean): ProjectSummary {
  return {
    id: PROJECT_ID,
    name: "Rajo Norte",
    crs: { code: "EPSG:32719", label_key: "crs.wgs84_utm_19s" },
    survey_count: 1,
    created_at: "2026-01-01T00:00:00Z",
    is_owner: isOwner,
  };
}

function survey(): SurveySummary {
  return {
    id: "s1",
    name: "vuelo.laz",
    capture_date: "2026-01-01",
    source_format: "laz",
    source_size_bytes: 100,
    status: "completed",
    current_stage: null,
    input_type: "point_cloud",
  };
}

function surveyDetail(): SurveyDetail {
  return { ...survey(), runs: [], latest_run: null };
}

function stubShared() {
  vi.spyOn(api, "listSurveys").mockResolvedValue([survey()]);
  vi.spyOn(api, "listCrs").mockResolvedValue([]);
  vi.spyOn(api, "listPendingUploads").mockResolvedValue([]);
  vi.spyOn(api, "getProcessingOptions").mockResolvedValue({ input_type: "point_cloud", options: [] });
  vi.spyOn(api, "listMembers").mockResolvedValue([]);
  vi.spyOn(api, "getSurvey").mockResolvedValue(surveyDetail());
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}`]}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("survey delete action", () => {
  it("hides the delete button for a non-owner", async () => {
    stubShared();
    vi.spyOn(api, "listProjects").mockResolvedValue([project(false)]);

    renderPage();

    await waitFor(() => expect(screen.getByText("vuelo.laz")).toBeTruthy());
    // The ConfirmDialog markup is always present (just unopened), so only the
    // row action button being absent means exactly one "Eliminar" node exists.
    expect(screen.getAllByText("Eliminar")).toHaveLength(1);
  });

  it("shows the delete button for an owner and only calls the API after confirming", async () => {
    stubShared();
    vi.spyOn(api, "listProjects").mockResolvedValue([project(true)]);
    const deleteSpy = vi.spyOn(api, "deleteSurvey").mockResolvedValue({});

    renderPage();

    await waitFor(() => expect(screen.getAllByText("Eliminar").length).toBeGreaterThan(0));
    // Row action is the first "Eliminar" in the DOM (the confirm dialog's own
    // button is always present, just not shown until opened).
    screen.getAllByText("Eliminar")[0].click();

    // Confirm dialog open, API not yet called
    await waitFor(() => expect(screen.getByText(/¿Eliminar el levantamiento/)).toBeTruthy());
    expect(deleteSpy).not.toHaveBeenCalled();

    const confirmButtons = screen.getAllByText("Eliminar");
    confirmButtons[confirmButtons.length - 1].click();

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("s1"));
  });
});
