"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

export type ThemeChoice = "system" | "light" | "dark";
export const THEME_KEY = "tia_theme";

const ORDER: ThemeChoice[] = ["system", "light", "dark"];
const LABEL: Record<ThemeChoice, string> = { system: "System", light: "Light", dark: "Dark" };

function apply(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

/**
 * Cycles System, Light, Dark. The choice is a per-browser preference kept in localStorage;
 * it is applied before first paint by the inline script in app/layout.tsx.
 */
export default function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>("system");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") setChoice(saved);
    } catch {
      /* storage unavailable: follow the system */
    }
  }, []);

  function next() {
    const n = ORDER[(ORDER.indexOf(choice) + 1) % ORDER.length];
    setChoice(n);
    apply(n);
    try {
      if (n === "system") window.localStorage.removeItem(THEME_KEY);
      else window.localStorage.setItem(THEME_KEY, n);
    } catch {
      /* ignore */
    }
  }

  const Icon = choice === "dark" ? Moon : choice === "light" ? Sun : Monitor;

  return (
    <button
      type="button"
      onClick={next}
      aria-label={`Theme: ${LABEL[choice]}. Activate to change.`}
      title={`Theme: ${LABEL[choice]}`}
      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors hover:bg-subtle hover:text-ink"
    >
      <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
    </button>
  );
}
