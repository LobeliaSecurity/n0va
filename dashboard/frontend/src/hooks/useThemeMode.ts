import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "n0va-dashboard-theme";

export type ThemeMode = "light" | "dark";

function readStored(): ThemeMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "dark" || v === "light") return v;
  } catch {
    /* ignore */
  }
  return "light";
}

export function useThemeMode() {
  const [mode, setModeState] = useState<ThemeMode>(() =>
    typeof document !== "undefined" ? readStored() : "light",
  );

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", mode === "dark");
    document.documentElement.style.colorScheme = mode === "dark" ? "dark" : "light";
  }, [mode]);

  return { mode, setMode };
}
