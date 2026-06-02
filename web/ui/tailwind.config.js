/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0A0E14",
        panel: "#111722",
        raised: "#161E2B",
        hairline: "#1E2733",
        "hairline-strong": "#2A3543",
        ink: "#E6EDF3",
        muted: "#8B98A9",
        faint: "#5A6677",
        accent: { DEFAULT: "#34D399", strong: "#10B981", dim: "#0c2a22" },
        cyan: "#22D3EE",
        warn: "#FBBF24",
        bad: "#FB7185",
        info: "#38BDF8",
        good: "#34D399",
      },
      fontFamily: {
        sans: ["'Inter Variable'", "Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: { xl: "12px", "2xl": "16px" },
      boxShadow: {
        glow: "0 0 0 1px rgba(52,211,153,0.25), 0 0 24px -6px rgba(52,211,153,0.35)",
        panel: "0 1px 0 0 rgba(255,255,255,0.02), 0 12px 32px -16px rgba(0,0,0,0.6)",
      },
      keyframes: {
        pulseDot: {
          "0%,100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(52,211,153,0.6)" },
          "50%": { opacity: "0.7", boxShadow: "0 0 0 5px rgba(52,211,153,0)" },
        },
        fadeUp: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        pulseDot: "pulseDot 1.8s ease-in-out infinite",
        fadeUp: "fadeUp 0.25s ease-out",
      },
    },
  },
  plugins: [],
};
