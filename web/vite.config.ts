import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `base: "./"` — Mini App tunnel ostida ham, to'g'ridan-to'g'ri ham ochiladi.
//
// Dev paytida `/api` so'rovlari FastAPI'ga uzatiladi (proxy). Shu tufayli
// frontend kodida manzil qattiq yozilmaydi va CORS umuman kerak emas:
// brauzer uchun hammasi bitta origin'dan kelayotgandek ko'rinadi.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
