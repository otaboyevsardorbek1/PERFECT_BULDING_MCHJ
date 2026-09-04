#!/usr/bin/env node
/**
 * 🏗️ Qurilish Korxonasi — Node.js Web Frontend (v3)
 *
 * Zero-dependency Node server:
 *  - web/public papkasidagi statik fayllarni xizmat qiladi (dashboard UI)
 *  - /api/* so'rovlarini Python (FastAPI) backend'iga proxylaydi
 *
 * Ishga tushirish:
 *   1) Backend (Python): uvicorn dashboard.app:app --port 8000
 *   2) Frontend (Node):  node web/server.js  (yoki npm start)
 *   -> http://localhost:3000
 *
 * Konfiguratsiya (env):
 *   PORT          - Node server porti (default 3000)
 *   PY_API_URL    - Python API manzili (default http://127.0.0.1:8000)
 */
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT || 3000;
const PY_API_URL = process.env.PY_API_URL || "http://127.0.0.1:8000";
const PUBLIC_DIR = path.join(__dirname, "public");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

/** Statik faylni o'qish */
function serveStatic(req, res) {
  let urlPath = decodeURIComponent(req.url.split("?")[0]);
  if (urlPath === "/") urlPath = "/index.html";

  // Path traversal himoyasi
  const safePath = path.normalize(urlPath).replace(/^(\.\.[\/\\])+/, "");
  const filePath = path.join(PUBLIC_DIR, safePath);
  if (!filePath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
    return res.end("403 Forbidden");
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      // SPA fallback -> index.html
      fs.readFile(path.join(PUBLIC_DIR, "index.html"), (err2, html) => {
        if (err2) {
          res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
          return res.end("404 Not Found");
        }
        res.writeHead(200, { "Content-Type": MIME[".html"] });
        res.end(html);
      });
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
    res.end(data);
  });
}

/** /api/* -> Python FastAPI'ga proxy */
function proxyApi(req, res) {
  const pyUrl = new URL(req.url, PY_API_URL);
  const headers = { ...req.headers, host: pyUrl.host };
  const proxyReq = http.request(
    pyUrl,
    { method: req.method, headers },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode, {
        "Content-Type": proxyRes.headers["content-type"] || "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
      });
      proxyRes.pipe(res);
    }
  );
  proxyReq.on("error", (e) => {
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({
      error: `Python backend'ga ulanishda xatolik: ${e.message}`,
      hint: `PY_API_URL=${PY_API_URL} manzilida uvicorn dashboard.app:app ishlayotganini tekshiring`,
    }));
  });
  req.pipe(proxyReq);
}

/** /health — servis holati */
function health(req, res) {
  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({
    status: "ok",
    node: true,
    python_api: PY_API_URL,
    time: new Date().toISOString(),
  }));
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  if (url.pathname === "/health") return health(req, res);
  if (url.pathname.startsWith("/api/")) return proxyApi(req, res);
  return serveStatic(req, res);
});

server.listen(PORT, () => {
  console.log(`🏗️  Node.js frontend ishga tushdi: http://localhost:${PORT}`);
  console.log(`🔌 Python API proxy: ${PY_API_URL}`);
  console.log(`📁 Static papka: ${PUBLIC_DIR}`);
});
