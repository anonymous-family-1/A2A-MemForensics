#!/usr/bin/env node

const { spawn } = require("child_process");
const { setTimeout: delay } = require("timers/promises");
const { randomUUID } = require("crypto");
const http = require("http");
const path = require("path");
const { argv, env, stdout } = require("process");

const rootDir = __dirname;
const hotelAgentUrl = env.HOTEL_AGENT_URL || "http://127.0.0.1:3201";
const decoyHotelAgentUrl = env.DECOY_HOTEL_AGENT_URL || "http://127.0.0.1:3202";

const agents = [
  {
    name: "Hotel Booking Agent",
    dir: path.join(rootDir, "hotel-booking-agent"),
    port: 3201,
  },
  {
    name: "Decoy Booking Agent",
    dir: path.join(rootDir, "decoy-booking-agent"),
    port: 3202,
  },
  {
    name: "Client Agent",
    dir: path.join(rootDir, "client-agent"),
    port: 3200,
    env: {
      HOTEL_AGENT_URL: hotelAgentUrl,
      DECOY_HOTEL_AGENT_URL: decoyHotelAgentUrl,
      OLLAMA_BASE_URL: env.OLLAMA_BASE_URL || "http://127.0.0.1:11434",
      OLLAMA_MODEL: env.OLLAMA_MODEL || "qwen3:14b",
      SIMULATE_AGENT_CARD_POISONING: env.SIMULATE_AGENT_CARD_POISONING || "0",
    },
  },
];

const startedProcesses = [];

function log(line = "") {
  stdout.write(`${line}\n`);
}

function extractTextFromTask(task) {
  const parts = task?.status?.message?.parts || [];
  return parts
    .filter((part) => part.kind === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

async function isAgentHealthy(port) {
  return await new Promise((resolve) => {
    const request = http.get(
      `http://127.0.0.1:${port}/.well-known/agent-card.json`,
      (response) => {
        response.resume();
        resolve((response.statusCode || 500) < 400);
      }
    );

    request.on("error", () => resolve(false));
    request.setTimeout(1000, () => {
      request.destroy();
      resolve(false);
    });
  });
}

async function waitForHealth(port) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    if (await isAgentHealthy(port)) {
      return;
    }
    await delay(500);
  }

  throw new Error(`Timed out waiting for agent on port ${port}`);
}

async function ensureAgentRunning(agent) {
  if (await isAgentHealthy(agent.port)) {
    log(`Using existing ${agent.name} on port ${agent.port}`);
    return;
  }

  log(`Starting ${agent.name} on port ${agent.port}`);
  const child = spawn("./node_modules/.bin/ts-node", ["src/index.ts"], {
    cwd: agent.dir,
    env: {
      ...env,
      PORT: String(agent.port),
      ...(agent.env || {}),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  startedProcesses.push(child);

  child.stdout.on("data", (chunk) => {
    const text = String(chunk).trim();
    if (text) {
      log(`[${agent.name}] ${text}`);
    }
  });

  child.stderr.on("data", (chunk) => {
    const text = String(chunk).trim();
    if (text) {
      log(`[${agent.name} stderr] ${text}`);
    }
  });

  child.on("exit", (code) => {
    if (code !== null && code !== 0) {
      log(`[${agent.name}] exited with code ${code}`);
    }
  });

  await waitForHealth(agent.port);
}

function cleanup() {
  for (const child of startedProcesses) {
    if (!child.killed) {
      child.kill("SIGINT");
    }
  }
}

async function sendClientRequest(query) {
  const payload = JSON.stringify({
    jsonrpc: "2.0",
    id: "1",
    method: "message/send",
    params: {
      message: {
        kind: "message",
        role: "user",
        messageId: randomUUID(),
        parts: [{ kind: "text", text: query }],
      },
    },
  });

  return await new Promise((resolve, reject) => {
    const request = http.request(
      "http://127.0.0.1:3200/",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(payload),
        },
      },
      (response) => {
        let data = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          data += chunk;
        });
        response.on("end", () => {
          try {
            const parsed = JSON.parse(data);
            resolve(extractTextFromTask(parsed.result));
          } catch (error) {
            reject(error);
          }
        });
      }
    );

    request.on("error", reject);
    request.write(payload);
    request.end();
  });
}

async function main() {
  const query = argv.slice(2).join(" ").trim();
  if (!query) {
    throw new Error('Usage: node run_pipeline.js "<booking request>"');
  }

  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);
  process.on("exit", cleanup);

  await ensureAgentRunning(agents[0]);
  await ensureAgentRunning(agents[1]);
  await ensureAgentRunning(agents[2]);

  log("");
  log("=== User Request ===");
  log(query);
  log("");
  log("=== Client Response ===");

  const result = await sendClientRequest(query);
  log(result);
}

main().catch((error) => {
  log(`Pipeline failed: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
