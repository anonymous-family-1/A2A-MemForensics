import type { AgentCard } from "@a2a-js/sdk";

export function createCurrencyAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Currency Agent",
    description: "A simple A2A currency conversion agent for travel demos.",
    url: `${baseUrl}/`,
    preferredTransport: "JSONRPC",
    provider: {
      organization: "Local Demo Currency Agent",
      url: "https://example.com/currency-agent",
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
        id: "convert_currency",
        name: "Convert Currency",
        description: "Converts USD to a requested target currency using live exchange rates.",
        tags: ["currency", "usd", "conversion", "travel"],
        examples: [
          "Convert 100 USD to EUR.",
          "How much is 250 USD in JPY?",
          "Convert 75 USD to BDT.",
        ],
        inputModes: ["text/plain"],
        outputModes: ["text/plain"],
      },
    ],
    supportsAuthenticatedExtendedCard: false,
  };
}
