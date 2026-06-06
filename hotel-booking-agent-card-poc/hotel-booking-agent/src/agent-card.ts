import type { AgentCard } from "@a2a-js/sdk";

export function createHotelBookingAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Hotel Booking Agent",
    description: "An A2A hotel booking agent for room reservations and stay management.",
    url: `${baseUrl}/`,
    preferredTransport: "JSONRPC",
    provider: {
      organization: "Hotel Booking Services",
      url: "https://example.com/hotel-booking-agent",
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
        id: "book_hotel",
        name: "Book Hotel",
        description: "Books a hotel using guest details, stay dates, and payment information.",
        tags: ["hotel", "booking", "reservation"],
        examples: [
          "Book a room at Grand Palace Hotel for John Smith from 2025-07-10 to 2025-07-13.",
        ],
        inputModes: ["text/plain"],
        outputModes: ["application/json", "text/plain"],
      },
    ],
    supportsAuthenticatedExtendedCard: false,
  };
}
