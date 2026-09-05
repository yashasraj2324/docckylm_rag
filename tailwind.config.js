/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0A0A0A",
          soft: "#171717",
          border: "#262626",
          muted: "#404040",
        },
        paper: {
          DEFAULT: "#FFFFFF",
          dark: "#F5F5F5",
        },
        gold: {
          DEFAULT: "#FACC15",
          dark: "#CA8A04",
          soft: "#FDE68A",
        },
        azure: {
          DEFAULT: "#2563EB",
          dark: "#1D4ED8",
          light: "#60A5FA",
        },
      },
    },
  },
  plugins: [],
};