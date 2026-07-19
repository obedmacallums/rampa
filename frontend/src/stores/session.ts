import { create } from "zustand";

import { api, ApiUser } from "../api/client";

interface SessionState {
  user: ApiUser | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<void>;
}

export const useSession = create<SessionState>((set) => ({
  user: null,
  ready: false,
  async login(username, password) {
    const { user } = await api.login(username, password);
    set({ user });
  },
  async logout() {
    await api.logout();
    set({ user: null });
  },
  async bootstrap() {
    try {
      const { user } = await api.me();
      set({ user, ready: true });
    } catch {
      set({ user: null, ready: true });
    }
  },
}));
