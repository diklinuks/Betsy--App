import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" so the build works under any GitHub Pages subpath (e.g. /Betsy/).
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { outDir: "dist", sourcemap: false },
});
