import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Design system tokens from docs/DESIGN.md
      colors: {
        canvas: "#0b0b0b",
        surface: "#212121",
        border: {
          subtle: "#212121",
          medium: "#353535",
        },
        text: {
          primary: "#ffffff",
          secondary: "#b9b9b9",
          tertiary: "#797979",
        },
        cta: "#f36458",
        interactive: "#0052ef",
        success: "#19d600",
        error: "#dd0000",
      },
    },
  },
  plugins: [],
};

export default config;
