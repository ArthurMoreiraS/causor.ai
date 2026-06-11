"use client";

import { useCallback, useEffect, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";
export type Density = "confortavel" | "compacta";

export interface Settings {
  theme: ThemeMode;
  density: Density;
  defaultOab: string;
  defaultUf: string;
  /** Anos usados no calendário forense / contagem de prazos. */
  calendarYears: number;
  /** Limiar (0..1) abaixo do qual a classificação da IA é sinalizada para revisão. */
  confidenceThreshold: number;
}

export const DEFAULT_SETTINGS: Settings = {
  theme: "light",
  density: "confortavel",
  defaultOab: "",
  defaultUf: "SP",
  calendarYears: 3,
  confidenceThreshold: 0.75
};

const STORAGE_KEY = "causor.settings.v1";

function readStored(): Settings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<Settings>;
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function resolveTheme(theme: ThemeMode): "light" | "dark" {
  if (theme === "system") {
    if (typeof window === "undefined") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return theme;
}

/** Applies theme + density to the document root so CSS can react via attributes. */
export function applySettings(settings: Settings) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = resolveTheme(settings.theme);
  document.documentElement.dataset.density = settings.density;
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  // Load once on mount (client only) and apply.
  useEffect(() => {
    const stored = readStored();
    setSettings(stored);
    applySettings(stored);
  }, []);

  // React to OS theme changes while in "system" mode.
  useEffect(() => {
    if (settings.theme !== "system" || typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applySettings(settings);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [settings]);

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore quota / privacy-mode errors */
      }
      applySettings(next);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setSettings(DEFAULT_SETTINGS);
    applySettings(DEFAULT_SETTINGS);
  }, []);

  return { settings, update, reset };
}
