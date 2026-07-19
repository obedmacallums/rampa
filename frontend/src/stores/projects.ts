import { create } from "zustand";

import { api, CrsEntry, ProjectSummary } from "../api/client";

interface ProjectsState {
  projects: ProjectSummary[];
  crsCatalog: CrsEntry[];
  fetch: () => Promise<void>;
  create: (name: string, crsId: number) => Promise<ProjectSummary>;
}

export const useProjects = create<ProjectsState>((set, get) => ({
  projects: [],
  crsCatalog: [],
  async fetch() {
    const [projects, crsCatalog] = await Promise.all([api.listProjects(), api.listCrs()]);
    set({ projects, crsCatalog });
  },
  async create(name, crsId) {
    const project = await api.createProject(name, crsId);
    set({ projects: [...get().projects, project] });
    return project;
  },
}));
