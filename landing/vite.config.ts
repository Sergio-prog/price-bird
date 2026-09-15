import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import tailwindcss from "@tailwindcss/vite";

const page = (path: string) => fileURLToPath(new URL(path, import.meta.url));

const brandQuery = (): Plugin => {
  const rewrite = (server: { middlewares: { use: (fn: (req: { url?: string }, res: unknown, next: () => void) => void) => void } }) => {
    server.middlewares.use((req, _res, next) => {
      if (req.url === "/?brand=true") req.url = "/brand/";
      next();
    });
  };
  return { name: "brand-query", configureServer: rewrite, configurePreviewServer: rewrite };
};

export default defineConfig({
  plugins: [tailwindcss(), brandQuery()],
  build: {
    rollupOptions: {
      input: {
        index: page("index.html"),
        brand: page("brand/index.html"),
      },
    },
  },
});
