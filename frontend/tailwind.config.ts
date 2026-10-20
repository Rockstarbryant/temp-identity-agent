import type { Config } from "tailwindcss";

/** Colour tokens are CSS variables (see app/globals.css) so light and dark themes share one set of class names. */
const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

/**
 * Design tokens. Every colour used by the UI comes from this file; components use the
 * semantic names (canvas, surface, ink, muted, line, accent, success, warning, danger)
 * and never raw hex values.
 *
 * `accent` (#6366F1) is the brand colour for focus rings and indicators.
 * `accent-fill` (#4F46E5 in both themes) is the background of filled buttons, so white text
 * keeps 4.5:1 contrast. `accent-strong` is the accent as text/link colour and is lighter in dark mode.
 * `danger-fill` plays the same role for destructive buttons.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: v("canvas"),
        surface: v("surface"),
        subtle: v("subtle"),
        ink: v("ink"),
        muted: v("muted"),
        line: { DEFAULT: v("line"), strong: v("line-strong") },
        accent: { DEFAULT: v("accent"), strong: v("accent-strong"), soft: v("accent-soft"), fill: v("accent-fill") },
        success: { DEFAULT: v("success"), soft: v("success-soft"), line: v("success-line") },
        warning: { DEFAULT: v("warning"), soft: v("warning-soft"), line: v("warning-line") },
        warm: v("warm"),
        deep: v("deep"),
        danger: { DEFAULT: v("danger"), soft: v("danger-soft"), line: v("danger-line"), fill: v("danger-fill") },
      },
      fontFamily: {
        display: ["ui-serif", "Iowan Old Style", "Palatino Linotype", "Palatino", "Georgia", "Cambria", "serif"],
        sans: [
          "Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto",
          "Helvetica Neue", "Arial", "sans-serif",
        ],
        mono: [
          "Geist Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "Liberation Mono", "monospace",
        ],
      },
      borderRadius: { DEFAULT: "6px", md: "6px", lg: "8px" },
      minHeight: { dvh: "100dvh" },
    },
  },
  plugins: [],
};

export default config;
