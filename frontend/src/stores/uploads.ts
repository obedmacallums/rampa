import { create } from "zustand";

import { api, PendingUpload } from "../api/client";

interface UploadsState {
  pendingByProject: Record<string, PendingUpload[]>;
  fetchPending: (projectId: string) => Promise<void>;
  cancel: (projectId: string, uploadSessionId: string) => Promise<void>;
}

export const useUploads = create<UploadsState>((set, get) => ({
  pendingByProject: {},
  async fetchPending(projectId) {
    const pending = await api.listPendingUploads(projectId);
    set({ pendingByProject: { ...get().pendingByProject, [projectId]: pending } });
  },
  async cancel(projectId, uploadSessionId) {
    await api.deleteUpload(projectId, uploadSessionId);
    const remaining = (get().pendingByProject[projectId] ?? []).filter(
      (upload) => upload.upload_session_id !== uploadSessionId,
    );
    set({ pendingByProject: { ...get().pendingByProject, [projectId]: remaining } });
  },
}));
