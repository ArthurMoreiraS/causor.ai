"use client";

import { useCallback, useEffect, useState } from "react";

export type Density = "confortavel" | "compacta";

export interface Settings {
  density: Density;
  defaultOab: string;
  defaultUf: string;
  /** Anos usados no calendário forense / contagem de prazos. */
  calendarYears: number;
  /** Limiar (0..1) abaixo do qual a classificação da IA é sinalizada para revisão. */
  confidenceThreshold: number;
}

export const DEFAULT_SETTINGS: Settings = {
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

/** Applies density to the document root so CSS can react via attributes. */
export function applySettings(settings: Settings) {
  if (typeof document === "undefined") return;
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
