import http from "http";
import express from "express";
import {
  DefaultRequestHandler,
  InMemoryTaskStore,
  TaskStore,
} from "@a2a-js/sdk/server";
import { A2AExpressApp } from "@a2a-js/sdk/server/express";
import { createHotelBookingAgentCard } from "./agent-card";
import { HotelBookingAgentExecutor } from "./agent-executor";

async function main() {
  const port = Number(process.env.PORT) || 3201;
  const baseUrl = process.env.PUBLIC_BASE_URL ?? `http://localhost:${port}`;

  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor = new HotelBookingAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    createHotelBookingAgentCard(baseUrl),
    taskStore,
    agentExecutor
  );

  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());
  const server = http.createServer(expressApp);

  server.listen(port, () => {
    console.log(`[HotelBookingAgent] Server started on ${baseUrl}`);
  });
}

main().catch((error) => {
  console.error("[HotelBookingAgent] Fatal error", error);
  process.exitCode = 1;
});
