// T023: project delete action is owner-only and gated by the confirm dialog
// (005 US2, mirrors ProjectMembers' remove-member confirm flow).
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import "../src/i18n";
import { api, ProjectSummary } from "../src/api/client";
import ProjectsPage from "../src/pages/ProjectsPage";
import { useProjects } from "../src/stores/projects";

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
  useProjects.setState({ projects: [], crsCatalog: [] });
});

function project(isOwner: boolean): ProjectSummary {
  return {
    id: "p1",
    name: "Rajo Norte",
    crs: { code: "EPSG:32719", label_key: "crs.wgs84_utm_19s" },
    survey_count: 2,
    created_at: "2026-01-01T00:00:00Z",
    is_owner: isOwner,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ProjectsPage />
    </MemoryRouter>,
  );
}

describe("project delete action", () => {
  it("hides the delete button for a non-owner", async () => {
    vi.spyOn(api, "listProjects").mockResolvedValue([project(false)]);
    vi.spyOn(api, "listCrs").mockResolvedValue([]);

    renderPage();

    await waitFor(() => expect(screen.getByText("Rajo Norte")).toBeTruthy());
    // The ConfirmDialog markup is always present (just unopened), so only the
    // row action button being absent means exactly one node exists.
    expect(screen.getAllByText("Eliminar proyecto")).toHaveLength(1);
  });

  it("shows the delete button for an owner and only calls the API after confirming", async () => {
    vi.spyOn(api, "listProjects").mockResolvedValue([project(true)]);
    vi.spyOn(api, "listCrs").mockResolvedValue([]);
    const deleteSpy = vi.spyOn(api, "deleteProject").mockResolvedValue({});

    renderPage();

    await waitFor(() => expect(screen.getAllByText("Eliminar proyecto").length).toBeGreaterThan(0));
    screen.getAllByText("Eliminar proyecto")[0].click();

    await waitFor(() => expect(screen.getByText(/¿Eliminar el proyecto/)).toBeTruthy());
    expect(deleteSpy).not.toHaveBeenCalled();

    const confirmButtons = screen.getAllByText("Eliminar proyecto");
    confirmButtons[confirmButtons.length - 1].click();

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("p1"));
  });
});
