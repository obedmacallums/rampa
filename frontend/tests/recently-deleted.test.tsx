// T034: Recently Deleted page renders listed projects/surveys and restoring
// calls the right endpoint and removes the row (US3).
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../src/i18n";
import { api, DeletedItems } from "../src/api/client";
import RecentlyDeletedPage from "../src/pages/RecentlyDeletedPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function items(): DeletedItems {
  const purgeAt = new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString();
  return {
    projects: [
      {
        id: "p1",
        name: "Rajo Norte",
        crs: { code: "EPSG:32719", label_key: "crs.wgs84_utm_19s" },
        survey_count: 2,
        deleted_at: new Date().toISOString(),
        purge_at: purgeAt,
      },
    ],
    surveys: [
      {
        id: "s1",
        name: "vuelo.laz",
        capture_date: "2026-01-01",
        project: { id: "p2", name: "Rajo Sur" },
        deleted_at: new Date().toISOString(),
        purge_at: purgeAt,
      },
    ],
  };
}

describe("RecentlyDeletedPage", () => {
  it("renders deleted projects and surveys with a restore action each", async () => {
    vi.spyOn(api, "listDeleted").mockResolvedValue(items());

    render(<RecentlyDeletedPage />);

    await waitFor(() => expect(screen.getByText("Rajo Norte")).toBeTruthy());
    expect(screen.getByText("vuelo.laz")).toBeTruthy();
    expect(screen.getByText("Rajo Sur")).toBeTruthy();
    expect(screen.getAllByText("Restaurar")).toHaveLength(2);
  });

  it("restoring a project calls restoreProject and removes it from the list", async () => {
    vi.spyOn(api, "listDeleted")
      .mockResolvedValueOnce(items())
      .mockResolvedValueOnce({ projects: [], surveys: items().surveys });
    const restoreSpy = vi.spyOn(api, "restoreProject").mockResolvedValue({
      id: "p1",
      name: "Rajo Norte",
      crs: { code: "EPSG:32719", label_key: "crs.wgs84_utm_19s" },
      survey_count: 2,
      created_at: new Date().toISOString(),
      is_owner: true,
    });

    render(<RecentlyDeletedPage />);

    await waitFor(() => expect(screen.getByText("Rajo Norte")).toBeTruthy());
    screen.getAllByText("Restaurar")[0].click();

    await waitFor(() => expect(restoreSpy).toHaveBeenCalledWith("p1"));
    await waitFor(() => expect(screen.queryByText("Rajo Norte")).toBeNull());
  });

  it("restoring a survey calls restoreSurvey and removes it from the list", async () => {
    vi.spyOn(api, "listDeleted")
      .mockResolvedValueOnce(items())
      .mockResolvedValueOnce({ projects: items().projects, surveys: [] });
    const restoreSpy = vi.spyOn(api, "restoreSurvey").mockResolvedValue({
      id: "s1",
      name: "vuelo.laz",
      capture_date: "2026-01-01",
      source_format: "laz",
      source_size_bytes: 1,
      status: "completed",
      current_stage: null,
      input_type: "point_cloud",
    });

    render(<RecentlyDeletedPage />);

    await waitFor(() => expect(screen.getByText("vuelo.laz")).toBeTruthy());
    screen.getAllByText("Restaurar")[1].click();

    await waitFor(() => expect(restoreSpy).toHaveBeenCalledWith("s1"));
    await waitFor(() => expect(screen.queryByText("vuelo.laz")).toBeNull());
  });
});
