import type { Config } from "tailwindcss";

/**
 * Design tokens. Every colour used by the UI comes from this file; components use the
 * semantic names (canvas, surface, ink, muted, line, accent, success, warning, danger)
 * and never raw hex values.
 *
 * `accent` (#6366F1) is the brand colour for focus rings and indicators.
 * `accent-strong` (#4F46E5) is used for filled buttons and text links, where white text
 * on #6366F1 would fall just under the 4.5:1 WCAG AA contrast ratio.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FAFAFA",
        surface: "#FFFFFF",
        subtle: "#F5F5F5",
        ink: "#171717",
        muted: "#737373",
        line: { DEFAULT: "#E5E5E5", strong: "#D4D4D4" },
        accent: { DEFAULT: "#6366F1", strong: "#4F46E5", soft: "#EEF2FF" },
        success: { DEFAULT: "#15803D", soft: "#F0FDF4", line: "#BBF7D0" },
        warning: { DEFAULT: "#B45309", soft: "#FFFBEB", line: "#FDE68A" },
        danger: { DEFAULT: "#B91C1C", soft: "#FEF2F2", line: "#FECACA" },
      },
      fontFamily: {
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
