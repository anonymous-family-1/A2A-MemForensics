import http from "http";
import express from "express";
import {
  DefaultRequestHandler,
  InMemoryTaskStore,
  TaskStore,
} from "@a2a-js/sdk/server";
import { A2AExpressApp } from "@a2a-js/sdk/server/express";
import { createCurrencyAgentCard } from "./agent-card";
import { CurrencyAgentExecutor } from "./agent-executor";

async function main() {
  const port = Number(process.env.PORT) || 3101;
  const baseUrl = process.env.PUBLIC_BASE_URL ?? `http://localhost:${port}`;

  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor = new CurrencyAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    createCurrencyAgentCard(baseUrl),
    taskStore,
    agentExecutor
  );

  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());
  const server = http.createServer(expressApp);

  server.listen(port, () => {
    console.log(`[CurrencyAgent] Server started on ${baseUrl}`);
  });
}

main().catch((error) => {
  console.error("[CurrencyAgent] Fatal error", error);
  process.exitCode = 1;
});
