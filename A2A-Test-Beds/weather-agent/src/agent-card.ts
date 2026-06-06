import type { AgentCard } from "@a2a-js/sdk";

export function createWeatherAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Weather Agent",
    description: "A simple A2A weather agent for travel preparation demos.",
    url: `${baseUrl}/`,
    preferredTransport: "JSONRPC",
    provider: {
      organization: "Local Demo Weather Agent",
      url: "https://example.com/weather-agent",
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
        id: "get_current_weather",
        name: "Get Current Weather",
        description: "Returns current weather conditions for a destination.",
        tags: ["weather", "current", "travel"],
        examples: ["What is the weather in Paris?"],
        inputModes: ["text/plain"],
        outputModes: ["text/plain"],
      },
      {
        id: "get_weather_forecast",
        name: "Get Weather Forecast",
        description:
          "Returns next-days weather forecasts for a destination.",
        tags: ["weather", "forecast", "travel"],
        examples: [
          "What is the weather in Paris?",
          "Give me the 3 day forecast for Tokyo.",
          "What is the 5 day forecast in LA, CA?",
        ],
        inputModes: ["text/plain"],
        outputModes: ["text/plain"],
      },
    ],
    supportsAuthenticatedExtendedCard: false,
  };
}
