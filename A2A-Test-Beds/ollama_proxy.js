#!/usr/bin/env node

const http = require("http");
const { URL } = require("url");

const listenHost = process.env.OLLAMA_PROXY_HOST || "0.0.0.0";
const listenPort = Number(process.env.OLLAMA_PROXY_PORT || "11434");
const targetBase = new URL(process.env.OLLAMA_TARGET_BASE || "http://127.0.0.1:11434");

const server = http.createServer((req, res) => {
  const targetUrl = new URL(req.url || "/", targetBase);
  const proxyReq = http.request(
    targetUrl,
    {
      method: req.method,
      headers: {
        ...req.headers,
        host: targetBase.host,
      },
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    }
  );

  proxyReq.on("error", (error) => {
    res.statusCode = 502;
    res.setHeader("content-type", "text/plain; charset=utf-8");
    res.end(`Ollama proxy error: ${error.message}`);
  });

  req.pipe(proxyReq);
});

server.listen(listenPort, listenHost, () => {
  process.stdout.write(
    `Ollama proxy listening on http://${listenHost}:${listenPort} -> ${targetBase.href}\n`
  );
});
