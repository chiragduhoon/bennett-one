/** Bennett brand tokens — colours sampled from the official logo. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bu: {
          blue: "#005098", blueDark: "#003a70", navy: "#0b1f3a", red: "#d81830", maroon: "#a01830",
          cyan: "#08a0e0", cream: "#fbf7ec", mist: "#f4f7fb",
        },
      },
      fontFamily: {
        display: ['"Poppins"', "system-ui", "sans-serif"],
        serif: ['"Cinzel"', '"Times New Roman"', "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
      },
      boxShadow: { card: "0 1px 2px rgba(11,31,58,.06), 0 8px 24px rgba(11,31,58,.06)" },
    },
  },
  plugins: [],
};
