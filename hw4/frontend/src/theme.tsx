import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type ThemeId = "heritage" | "gameday" | "night";

export type Theme = {
  id: ThemeId;
  label: string;
  tagline: string;
  /** Two swatches for the switcher, so the choice is visible before it is made. */
  swatch: [string, string];
};

export const THEMES: Theme[] = [
  {
    id: "heritage",
    label: "1900s Heritage",
    tagline: "Laid paper, old ink, a light serif",
    swatch: ["#faf7f0", "#00356b"],
  },
  {
    id: "gameday",
    label: "Game Day",
    tagline: "Bunting stripes and heavy type",
    swatch: ["#0f4d9e", "#e8a317"],
  },
  {
    id: "night",
    label: "Gameday Night",
    tagline: "The bowl under floodlights",
    swatch: ["#0a1526", "#4d8ff0"],
  },
];

const STORAGE_KEY = "cc-theme";
const DEFAULT_THEME: ThemeId = "heritage";

function readStored(): ThemeId {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    if (saved && THEMES.some((t) => t.id === saved)) return saved;
  } catch {
    /* private browsing can throw on localStorage access */
  }
  return DEFAULT_THEME;
}

type ThemeState = { theme: ThemeId; setTheme: (id: ThemeId) => void };

const ThemeContext = createContext<ThemeState | null>(null);

/**
 * Applies the chosen theme as `data-theme` on <html>.
 *
 * Writing the attribute rather than inline styles means the whole page restyles
 * from CSS alone — no component needs to know a theme exists, and a new theme is
 * a block of custom properties in index.css.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(readStored);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* not fatal — the theme just will not persist */
    }
  }, [theme]);

  const setTheme = useCallback((id: ThemeId) => setThemeState(id), []);
  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
