import { create } from "zustand";

import { api, PendingUpload } from "../api/client";

interface UploadsState {
  pendingByProject: Record<string, PendingUpload[]>;
  fetchPending: (projectId: string) => Promise<void>;
}

export const useUploads = create<UploadsState>((set, get) => ({
  pendingByProject: {},
  async fetchPending(projectId) {
    const pending = await api.listPendingUploads(projectId);
    set({ pendingByProject: { ...get().pendingByProject, [projectId]: pending } });
  },
}));
