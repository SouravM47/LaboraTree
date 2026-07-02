import type { Config } from "tailwindcss";

// Light forest theme — derived from the Laboratree logo (tree growing from a lab flask).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#FBFDF9",
        forest: "#14342A",
        leaf: "#6DB33F",
        sprout: "#A8D08D",
        ink: "#1E2A22",
        muted: "#5B6B60",
        line: "#E4EBE1",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-lora)", "Georgia", "serif"],
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem",
      },
    },
  },
  plugins: [],
};

export default config;
