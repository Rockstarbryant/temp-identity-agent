import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f1115",
        paper: "#fafaf9",
        accent: "#4f46e5",
      },
    },
  },
  plugins: [],
};

export default config;
