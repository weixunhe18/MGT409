import { useEffect, useRef, useState } from "react";

import { THEMES, useTheme } from "../theme";
import "./ThemeSwitcher.css";

/** Spirit picker in the nav bar. Shows the current mood and swaps the whole site. */
export default function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = THEMES.find((t) => t.id === theme) ?? THEMES[0];

  // Close on outside click or Escape, as a menu should.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="spirit" ref={ref}>
      <button
        type="button"
        className="spirit__button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`School spirit: ${current.label}. Change theme.`}
      >
        <span className="spirit__dots" aria-hidden="true">
          <span style={{ background: current.swatch[0] }} />
          <span style={{ background: current.swatch[1] }} />
        </span>
        <span className="spirit__label">{current.label}</span>
      </button>

      {open && (
        <ul className="spirit__menu" role="listbox" aria-label="School spirit">
          {THEMES.map((option) => (
            <li key={option.id}>
              <button
                type="button"
                role="option"
                aria-selected={option.id === theme}
                className={
                  option.id === theme ? "spirit__option spirit__option--on" : "spirit__option"
                }
                onClick={() => {
                  setTheme(option.id);
                  setOpen(false);
                }}
              >
                <span className="spirit__dots" aria-hidden="true">
                  <span style={{ background: option.swatch[0] }} />
                  <span style={{ background: option.swatch[1] }} />
                </span>
                <span className="spirit__text">
                  <strong>{option.label}</strong>
                  <em>{option.tagline}</em>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
