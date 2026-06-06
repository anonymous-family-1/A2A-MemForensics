import http from "http";
import express from "express";
import {
  DefaultRequestHandler,
  InMemoryTaskStore,
  TaskStore,
} from "@a2a-js/sdk/server";
import { A2AExpressApp } from "@a2a-js/sdk/server/express";
import { createPlannerAgentCard } from "./agent-card";
import { PlannerAgentExecutor } from "./agent-executor";

async function main() {
  const port = Number(process.env.PORT) || 3103;
  const baseUrl = process.env.PUBLIC_BASE_URL ?? `http://localhost:${port}`;

  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor = new PlannerAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    createPlannerAgentCard(baseUrl),
    taskStore,
    agentExecutor
  );

  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());
  const server = http.createServer(expressApp);

  server.listen(port, () => {
    console.log(`[PlannerAgent] Server started on ${baseUrl}`);
  });
}

main().catch((error) => {
  console.error("[PlannerAgent] Fatal error", error);
  process.exitCode = 1;
});
