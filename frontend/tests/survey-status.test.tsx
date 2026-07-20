// T025: SurveyStatus renders per-option state badges and the failing
// option's translated message, even when the run as a whole is failed
// (per-option publication, FR-009/FR-010, SC-006, quickstart Scenario 4).
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../src/i18n";
import { api, SurveyDetail } from "../src/api/client";
import SurveyStatus from "../src/components/SurveyStatus";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function failedRunDetail(): SurveyDetail {
  return {
    id: "s1",
    name: "vuelo.laz",
    capture_date: "2026-01-01",
    source_format: "laz",
    source_size_bytes: 100,
    status: "failed",
    current_stage: null,
    input_type: "point_cloud",
    runs: [],
    latest_run: {
      id: "r1",
      number: 1,
      stage: "surface_generation",
      state: "failed",
      input_type: "point_cloud",
      failure_code: "internal_error",
      failure_message_key: "errors.internal_error",
      started_at: null,
      finished_at: null,
      options: [
        {
          option_id: "elevation",
          state: "completed",
          failure_code: null,
          failure_message_key: null,
          started_at: null,
          finished_at: null,
          reused_from_run_id: null,
        },
        {
          option_id: "hillshade",
          state: "completed",
          failure_code: null,
          failure_message_key: null,
          started_at: null,
          finished_at: null,
          reused_from_run_id: null,
        },
        {
          option_id: "point_cloud_3d",
          state: "failed",
          failure_code: "internal_error",
          failure_message_key: "errors.internal_error",
          started_at: null,
          finished_at: null,
          reused_from_run_id: null,
        },
      ],
    },
  };
}

describe("SurveyStatus", () => {
  it("renders each option's state and the failing option's message", async () => {
    vi.spyOn(api, "getSurvey").mockResolvedValue(failedRunDetail());

    render(<SurveyStatus surveyId="s1" />);

    await waitFor(() => {
      expect(screen.queryByText("Elevación")).toBeTruthy();
    });
    expect(screen.getByText("Relieve sombreado")).toBeTruthy();
    expect(screen.getByText("Nube de puntos 3D")).toBeTruthy();

    // completed options are visible even though the run as a whole failed
    expect(screen.getAllByText("Completado")).toHaveLength(2);

    // the failing option's translated message renders (may also appear in
    // the retry prompt below — assert at least once, not an exact count)
    expect(
      screen.getAllByText(/Ocurrió un error durante el procesamiento/).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("shows a retry action when the survey failed", async () => {
    vi.spyOn(api, "getSurvey").mockResolvedValue(failedRunDetail());

    render(<SurveyStatus surveyId="s1" />);

    await waitFor(() => {
      expect(screen.queryByText("Reintentar procesamiento")).toBeTruthy();
    });
  });
});
