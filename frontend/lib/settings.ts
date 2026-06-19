"use client";

import { useCallback, useEffect, useState } from "react";

export interface Settings {
  defaultOab: string;
  defaultUf: string;
  /** Limiar (0..1) abaixo do qual a classificação da IA é sinalizada para revisão. */
  confidenceThreshold: number;
}

export const DEFAULT_SETTINGS: Settings = {
  defaultOab: "",
  defaultUf: "SP",
  confidenceThreshold: 0.75
};

/** Anos de calendário forense carregados na contagem de prazos (default fixo). */
export const CALENDAR_YEARS = 3;

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

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  // Load once on mount (client only).
  useEffect(() => {
    setSettings(readStored());
  }, []);

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore quota / privacy-mode errors */
      }
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
  }, []);

  return { settings, update, reset };
}
