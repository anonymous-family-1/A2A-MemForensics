import type { AgentCard } from "@a2a-js/sdk";

export function createClientAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Client Agent",
    description: "An A2A client agent that uses Ollama to prepare hotel-booking requests.",
    url: `${baseUrl}/`,
    preferredTransport: "JSONRPC",
    provider: {
      organization: "Booking Orchestration Services",
      url: "https://example.com/client-agent",
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
        id: "book_hotel_via_orchestration",
        name: "Book Hotel Via Orchestration",
        description: "Extracts booking details, discovers the hotel agent, and places the booking over A2A.",
        tags: ["hotel", "booking", "ollama", "orchestration"],
        examples: [
          "Book the Grand Palace Hotel in Paris for John Smith. My email is john@example.com and my card is 4111111111111111.",
        ],
        inputModes: ["text/plain"],
        outputModes: ["application/json", "text/plain"],
      },
    ],
    supportsAuthenticatedExtendedCard: false,
  };
}
