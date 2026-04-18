import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#050810",
          900: "#080c16",
          800: "#0b1220",
          700: "#111a2e",
          600: "#18233d",
        },
        rail: "#0b1220",
        pitch: {
          DEFAULT: "#0f2b1d",
          deep: "#0a1e14",
          line: "#22c55e",
        },
        accent: {
          DEFAULT: "#4ade80",
          soft: "#86efac",
          deep: "#16a34a",
        },
        electric: {
          DEFAULT: "#22d3ee",
          soft: "#67e8f9",
        },
        magenta: {
          DEFAULT: "#e879f9",
          soft: "#f0abfc",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        display: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      letterSpacing: {
        tightest: "-0.035em",
      },
      boxShadow: {
        glow: "0 0 60px -12px rgba(74, 222, 128, 0.45)",
        card: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 0 0 1px rgba(255,255,255,0.06), 0 20px 60px -20px rgba(0,0,0,0.6)",
      },
      backgroundImage: {
        "mesh-primary":
          "radial-gradient(at 18% 12%, rgba(34, 211, 238, 0.18) 0px, transparent 45%), radial-gradient(at 82% 8%, rgba(74, 222, 128, 0.18) 0px, transparent 45%), radial-gradient(at 50% 100%, rgba(232, 121, 249, 0.14) 0px, transparent 55%)",
        "grid-lines":
          "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "32px 32px",
      },
      animation: {
        "pulse-soft": "pulse-soft 3s ease-in-out infinite",
        "gradient-shift": "gradient-shift 12s ease infinite",
      },
      keyframes: {
        "pulse-soft": {
          "0%, 100%": { opacity: "0.75" },
          "50%": { opacity: "1" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
