"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Local-only minuta edits, keyed by petition id.
 *
 * There is no backend endpoint to persist petition content yet, so edits live
 * in the browser. The UI labels these clearly as local drafts and the filing
 * gate keeps using server content until a sync endpoint exists.
 */

const STORAGE_KEY = "causor.localDrafts.v1";

type DraftMap = Record<number, string>;

function readAll(): DraftMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DraftMap) : {};
  } catch {
    return {};
  }
}

function writeAll(map: DraftMap) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore quota / privacy-mode errors */
  }
}

export function useLocalDrafts() {
  const [drafts, setDrafts] = useState<DraftMap>({});

  useEffect(() => {
    setDrafts(readAll());
  }, []);

  const save = useCallback((id: number, content: string) => {
    setDrafts((prev) => {
      const next = { ...prev, [id]: content };
      writeAll(next);
      return next;
    });
  }, []);

  const clear = useCallback((id: number) => {
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[id];
      writeAll(next);
      return next;
    });
  }, []);

  return { drafts, save, clear };
}
