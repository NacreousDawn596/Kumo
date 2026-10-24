import { create } from "zustand";
import { api } from "../api/client";

export const useAuth = create((set) => ({
  user: null,
  loading: true,
  initialized: false,

  async loadUser() {
    try {
      const user = await api("/api/auth/me");
      set({ user, loading: false, initialized: true });
    } catch {
      set({ user: null, loading: false, initialized: true });
    }
  },

  setUser(user) {
    set({ user });
  },

  async login(email, password) {
    const user = await api("/api/auth/login", { method: "POST", body: { email, password } });
    set({ user });
    return user;
  },

  async register(payload) {
    const user = await api("/api/auth/register", { method: "POST", body: payload });
    set({ user });
    return user;
  },

  async logout() {
    await api("/api/auth/logout", { method: "POST" });
    set({ user: null });
  },
}));
