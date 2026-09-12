import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const leanPhaserRuntime = fileURLToPath(
  new URL("./node_modules/phaser/dist/phaser-arcade-physics.js", import.meta.url)
);

export default defineConfig({
  resolve: {
    alias: [
      { find: /^phaser$/, replacement: leanPhaserRuntime }
    ]
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000"
    }
  }
});
