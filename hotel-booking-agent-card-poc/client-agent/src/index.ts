import http from "http";
import express from "express";
import {
  DefaultRequestHandler,
  InMemoryTaskStore,
  TaskStore,
} from "@a2a-js/sdk/server";
import { A2AExpressApp } from "@a2a-js/sdk/server/express";
import { createClientAgentCard } from "./agent-card";
import { ClientAgentExecutor } from "./agent-executor";

async function main() {
  const port = Number(process.env.PORT) || 3200;
  const baseUrl = process.env.PUBLIC_BASE_URL ?? `http://localhost:${port}`;

  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor = new ClientAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    createClientAgentCard(baseUrl),
    taskStore,
    agentExecutor
  );

  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());
  const server = http.createServer(expressApp);

  server.listen(port, () => {
    console.log(`[ClientAgent] Server started on ${baseUrl}`);
  });
}

main().catch((error) => {
  console.error("[ClientAgent] Fatal error", error);
  process.exitCode = 1;
});
