import { createContext, useContext, type ReactNode } from "react";

import { useThemeMode, type ThemeMode } from "@/hooks/useThemeMode";

type ThemeModeContextValue = {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
};

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null);

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const { mode, setMode } = useThemeMode();
  return <ThemeModeContext.Provider value={{ mode, setMode }}>{children}</ThemeModeContext.Provider>;
}

export function useThemeModeContext(): ThemeModeContextValue {
  const v = useContext(ThemeModeContext);
  if (!v) {
    throw new Error("useThemeModeContext must be used within ThemeModeProvider");
  }
  return v;
}
