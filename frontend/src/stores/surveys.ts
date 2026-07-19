import { create } from "zustand";

import { api, SurveySummary } from "../api/client";

interface SurveysState {
  byProject: Record<string, SurveySummary[]>;
  fetch: (projectId: string) => Promise<void>;
}

export const useSurveys = create<SurveysState>((set, get) => ({
  byProject: {},
  async fetch(projectId) {
    const surveys = await api.listSurveys(projectId);
    set({ byProject: { ...get().byProject, [projectId]: surveys } });
  },
}));
