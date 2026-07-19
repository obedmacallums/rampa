import { create } from "zustand";

import { api, ApiError, MemberRole, ProjectMember } from "../api/client";

interface MembersState {
  members: ProjectMember[];
  error: string | null; // i18n message key of the last failed mutation
  load: (projectId: string) => Promise<void>;
  add: (projectId: string, username: string, role: MemberRole) => Promise<boolean>;
  updateRole: (projectId: string, username: string, role: MemberRole) => Promise<boolean>;
  remove: (projectId: string, username: string) => Promise<boolean>;
}

export const useMembers = create<MembersState>((set, get) => {
  // run a mutation, reload on success, surface the message key on failure
  async function mutate(projectId: string, action: () => Promise<unknown>): Promise<boolean> {
    try {
      await action();
      set({ error: null });
      await get().load(projectId);
      return true;
    } catch (error) {
      set({ error: error instanceof ApiError ? error.messageKey : "errors.invalid_request" });
      return false;
    }
  }

  return {
    members: [],
    error: null,

    async load(projectId) {
      set({ members: await api.listMembers(projectId) });
    },
    add: (projectId, username, role) =>
      mutate(projectId, () => api.addMember(projectId, username, role)),
    updateRole: (projectId, username, role) =>
      mutate(projectId, () => api.updateMemberRole(projectId, username, role)),
    remove: (projectId, username) => mutate(projectId, () => api.removeMember(projectId, username)),
  };
});
