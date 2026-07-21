"use client";

import { useEffect, useState } from "react";
import { EnrichMode } from "@/src/lib/types";

const STORAGE_KEY = "hyrepath.enrichMode";

export function useEnrichMode() {
  const [mode, setModeState] = useState<EnrichMode>("async");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "sync" || stored === "async") {
      setModeState(stored);
    }
    setReady(true);
  }, []);

  const setMode = (next: EnrichMode) => {
    setModeState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  return { mode, setMode, ready };
}
