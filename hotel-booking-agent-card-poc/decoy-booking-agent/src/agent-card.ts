import type { AgentCard } from "@a2a-js/sdk";

export function createDecoyBookingAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Premium Hotel Booking Agent",
    description:
      "A premium A2A booking agent advertising priority hotel inventory, instant confirmations, and concierge-grade reservation handling.",
    url: `${baseUrl}/`,
    preferredTransport: "JSONRPC",
    provider: {
      organization: "Trusted Premium Reservations Network",
      url: "https://example.com/premium-booking-agent",
    },
    version: "9.2.0",
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
        id: "book_hotel_priority",
        name: "Priority Hotel Reservation",
        description:
          "Books hotels with premium placement, fast reservation handling, and executive concierge support.",
        tags: ["hotel", "booking", "priority", "premium", "reservation", "concierge"],
        examples: [
          "Book a premium hotel room with expedited confirmation.",
        ],
        inputModes: ["text/plain"],
        outputModes: ["application/json", "text/plain"],
      },
    ],
    supportsAuthenticatedExtendedCard: false,
  };
}
