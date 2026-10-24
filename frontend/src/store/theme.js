import { create } from "zustand";

const getInitialTheme = () => {
  const stored = localStorage.getItem("kumo-theme");
  if (stored === "light" || stored === "dark" || stored === "system") return stored;
  return "system";
};

const resolveTheme = (pref) => {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  }
  return pref;
};

export const useTheme = create((set, get) => ({
  preference: getInitialTheme(),
  resolved: "dark",

  apply(pref) {
    const resolved = resolveTheme(pref);
    document.documentElement.setAttribute("data-theme", resolved);
    set({ preference: pref, resolved });
    if (pref === "system") localStorage.removeItem("kumo-theme");
    else localStorage.setItem("kumo-theme", pref);
  },

  init() {
    const resolved = resolveTheme(get().preference);
    document.documentElement.setAttribute("data-theme", resolved);
    set({ resolved });
    window
      .matchMedia("(prefers-color-scheme: light)")
      .addEventListener("change", () => {
        if (get().preference === "system") {
          const r = resolveTheme("system");
          document.documentElement.setAttribute("data-theme", r);
          set({ resolved: r });
        }
      });
  },
}));
