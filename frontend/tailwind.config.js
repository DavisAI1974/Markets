/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        regime: {
          equilibrium: "#3b82f6",   // blue-500
          whale_up: "#22c55e",      // green-500
          whale_down: "#ef4444",    // red-500
          herd_up: "#f97316",       // orange-500
          herd_down: "#b91c1c",     // dark red
          wash: "#eab308",          // yellow-500
          depleted: "#9ca3af",      // gray-400
          unknown: "#6b7280",       // gray-500
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
