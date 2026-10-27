import { create } from "zustand";

const ACCENTS = ["purple", "blue", "indigo", "teal", "green", "orange", "rose", "cyan"];

function read(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : v;
  } catch {
    return fallback;
  }
}

function resolveMode(mode) {
  if (mode === "system") {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return mode;
}

const initial = {
  mode: read("kumo-mode", "system"),
  accent: read("kumo-accent", "purple"),
  radiusScale: parseFloat(read("kumo-radius", "1")) || 1,
  fontScale: parseFloat(read("kumo-font", "1")) || 1,
};

export const useTheme = create((set, get) => ({
  ...initial,
  resolved: "dark",

  apply(prefs) {
    const merged = { ...get(), ...prefs };
    const resolved = resolveMode(merged.mode);

    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.setAttribute("data-accent", merged.accent);
    document.documentElement.style.setProperty("--radius-scale", String(merged.radiusScale));
    document.documentElement.style.setProperty("--font-scale", String(merged.fontScale));

    // Persist
    try {
      localStorage.setItem("kumo-mode", merged.mode);
      localStorage.setItem("kumo-accent", merged.accent);
      localStorage.setItem("kumo-radius", String(merged.radiusScale));
      localStorage.setItem("kumo-font", String(merged.fontScale));
    } catch {}

    set(merged);
  },

  setMode(mode) {
    get().apply({ mode });
  },
  setAccent(accent) {
    if (ACCENTS.includes(accent)) get().apply({ accent });
  },
  setRadius(scale) {
    const clamped = Math.min(2, Math.max(0.5, Number(scale) || 1));
    get().apply({ radiusScale: clamped });
  },
  setFontScale(scale) {
    const clamped = Math.min(1.4, Math.max(0.85, Number(scale) || 1));
    get().apply({ fontScale: clamped });
  },

  init() {
    get().apply({});
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
      if (get().mode === "system") get().apply({});
    });
  },
}));

export { ACCENTS };
