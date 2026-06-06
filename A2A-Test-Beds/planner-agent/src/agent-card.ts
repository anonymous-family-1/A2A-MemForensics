import type { AgentCard } from "@a2a-js/sdk";

export function createPlannerAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Planner Agent",
    description: "A simple A2A planner that coordinates travel helper agents.",
    url: `${baseUrl}/`,
    preferredTransport: "JSONRPC",
    provider: {
      organization: "Local Demo Planner Agent",
      url: "https://example.com/planner-agent",
    },
    version: "1.0.0",
    protocolVersion: "0.3.0",
    capabilities: {
      streaming: true,
      pushNotifications: false,
      stateTransitionHistory: true,
    },
    securitySchemes: undefined,
    security: undefined,
    defaultInputModes: ["text/plain"],
    defaultOutputModes: ["application/json", "text/plain"],
    skills: [
      {
        id: "prepare_trip",
        name: "Prepare Trip",
        description: "Coordinates weather, currency, and time agents for a trip.",
        tags: ["planner", "travel", "orchestration"],
        examples: ["I am traveling to Paris with 100 USD. Help me prepare."],
        inputModes: ["text/plain"],
        outputModes: ["application/json", "text/plain"],
      },
    ],
    supportsAuthenticatedExtendedCard: false,
  };
}
