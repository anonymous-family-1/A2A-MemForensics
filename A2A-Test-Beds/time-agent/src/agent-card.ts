import type { AgentCard } from "@a2a-js/sdk";

export function createTimeAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Time Agent",
    description: "A simple A2A local-time agent for travel preparation demos.",
    url: `${baseUrl}/`,
    preferredTransport: "JSONRPC",
    provider: {
      organization: "Local Demo Time Agent",
      url: "https://example.com/time-agent",
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
    defaultOutputModes: ["text/plain"],
    skills: [
      {
        id: "get_local_time",
        name: "Get Local Time",
        description: "Returns the current local time for a destination.",
        tags: ["time", "travel", "timezone"],
        examples: [
          "What time is it in Paris?",
          "What is the local time in Tokyo?",
          "Time in LA, CA",
        ],
        inputModes: ["text/plain"],
        outputModes: ["text/plain"],
      },
    ],
    supportsAuthenticatedExtendedCard: false,
  };
}
