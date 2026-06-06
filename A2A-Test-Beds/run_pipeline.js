#!/usr/bin/env node

const { spawn } = require("child_process");
const { setTimeout: delay } = require("timers/promises");
const { randomUUID } = require("crypto");
const http = require("http");
const path = require("path");
const { stdout, argv, env } = require("process");

const rootDir = __dirname;

const agents = [
  {
    name: "Weather Agent",
    dir: path.join(rootDir, "weather-agent"),
    port: 3100,
  },
  {
    name: "Currency Agent",
    dir: path.join(rootDir, "currency-agent"),
    port: 3101,
  },
  {
    name: "Time Agent",
    dir: path.join(rootDir, "time-agent"),
    port: 3102,
  },
  {
    name: "Planner Agent",
    dir: path.join(rootDir, "planner-agent"),
    port: 3103,
    env: {
      WEATHER_AGENT_URL: "http://127.0.0.1:3100",
      CURRENCY_AGENT_URL: "http://127.0.0.1:3101",
      TIME_AGENT_URL: "http://127.0.0.1:3102",
      OLLAMA_BASE_URL: env.OLLAMA_BASE_URL || "http://127.0.0.1:11434",
      OLLAMA_MODEL: env.OLLAMA_MODEL || "qwen3:14b",
    },
  },
];

const startedProcesses = [];

function normalizeMode(value) {
  const normalized = (value || "rule-based").trim().toLowerCase();
  if (normalized === "ollama") {
    return "ollama";
  }
  return "rule-based";
}

function normalizeAgent(value) {
  const normalized = (value || "all").trim().toLowerCase();
  if (["weather", "weather-agent", "weather agent"].includes(normalized)) {
    return "weather-agent";
  }
  if (["currency", "currency-agent", "currency agent"].includes(normalized)) {
    return "currency-agent";
  }
  if (["time", "time-agent", "time agent"].includes(normalized)) {
    return "time-agent";
  }
  return "all";
}

function parseArgs() {
  const rawArgs = argv.slice(2);
  let agent = "all";
  let mode = "rule-based";
  const queryParts = [];

  for (let index = 0; index < rawArgs.length; index += 1) {
    const arg = rawArgs[index];
    if (arg === "--mode") {
      mode = normalizeMode(rawArgs[index + 1]);
      index += 1;
      continue;
    }
    if (arg === "--agent") {
      agent = normalizeAgent(rawArgs[index + 1]);
      index += 1;
      continue;
    }
    queryParts.push(arg);
  }

  return {
    agent,
    mode,
    query: queryParts.join(" ").trim(),
  };
}

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

async function isOllamaHealthy(baseUrl) {
  return await new Promise((resolve) => {
    const request = http.get(baseUrl, (response) => {
      response.resume();
      resolve((response.statusCode || 500) < 500);
    });

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

async function ensureOllamaRunning() {
  const baseUrl = env.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
  if (await isOllamaHealthy(baseUrl)) {
    log(`Using existing Ollama service at ${baseUrl}`);
    return;
  }

  throw new Error(
    `Ollama service is not reachable at ${baseUrl}. Start ollama serve on the Ollama host and make sure it is listening on a network-reachable address.`
  );
}

function cleanup() {
  for (const child of startedProcesses) {
    if (!child.killed) {
      child.kill("SIGINT");
    }
  }
}

async function sendPlannerRequest(query, selectedAgent, selectedMode) {
  const plannerInput = [
    `Execution mode: ${selectedMode}`,
    `Target agent: ${selectedAgent}`,
    "",
    "User goal:",
    query,
  ].join("\n");
  const payload = JSON.stringify({
    jsonrpc: "2.0",
    id: "1",
    method: "message/send",
    params: {
      message: {
        kind: "message",
        role: "user",
        messageId: randomUUID(),
        parts: [{ kind: "text", text: plannerInput }],
      },
    },
  });

  return await new Promise((resolve, reject) => {
    const request = http.request(
      "http://127.0.0.1:3103/",
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
  const { agent: selectedAgent, mode: selectedMode, query } = parseArgs();
  if (!query) {
    throw new Error("Provide a user request.");
  }

  try {
    if (selectedMode === "ollama") {
      await ensureOllamaRunning();
    }

    const agentsToStart = agents.filter((agent) => {
      if (agent.name === "Planner Agent") {
        return true;
      }

      if (selectedAgent === "all") {
        return true;
      }

      return (
        (selectedAgent === "weather-agent" && agent.name === "Weather Agent") ||
        (selectedAgent === "currency-agent" && agent.name === "Currency Agent") ||
        (selectedAgent === "time-agent" && agent.name === "Time Agent")
      );
    });

    for (const agent of agentsToStart) {
      await ensureAgentRunning(agent);
    }

    const result = await sendPlannerRequest(query, selectedAgent, selectedMode);
    log("\nPlanner result:\n");
    log(result);
  } finally {
    cleanup();
  }
}

main().catch((error) => {
  log(`Pipeline failed: ${error instanceof Error ? error.message : String(error)}`);
  cleanup();
  process.exitCode = 1;
});
