import { v4 as uuidv4 } from "uuid";
import { Task, TaskStatusUpdateEvent } from "@a2a-js/sdk";
import {
  AgentExecutor,
  ExecutionEventBus,
  RequestContext,
} from "@a2a-js/sdk/server";
import { getForecast, getWeather } from "./weather-api";

const FORECAST_HINTS = [
  "forecast",
  "forecasts",
  "forcast",
  "forcasts",
  "tomorrow",
  "week",
  "rain",
  "snow",
];

function wantsForecast(text: string): boolean {
  const lower = text.toLowerCase();
  return (
    FORECAST_HINTS.some((hint) => lower.includes(hint)) ||
    /\b(?:next|for|over)\s+\d+\s+days?\b/.test(lower) ||
    /\b\d+\s+day\s+(?:forecast|forecasts|forcast|forcasts)\b/.test(lower)
  );
}

function extractForecastDays(text: string): number {
  const lower = text.toLowerCase();
  const explicitDayMatch = lower.match(
    /\b(?:next|for|forecast(?:\s+for)?|over)\s+(\d+)\s+days?\b/
  );
  if (explicitDayMatch) {
    return Number(explicitDayMatch[1]);
  }

  const standaloneDayMatch = lower.match(/\b(\d+)\s+day forecast\b/);
  if (standaloneDayMatch) {
    return Number(standaloneDayMatch[1]);
  }

  if (lower.includes("tomorrow")) {
    return 2;
  }

  return 5;
}

function extractCity(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  const prepositionMatch = normalized.match(
    /\b(?:in|for|at)\b\s+(.+?)(?=$|[?!]|\.(?:\s|$)|\b(?:today|tomorrow|right now|currently|now|this week|next week|for the next \d+\s+days?|for \d+\s+days?|next \d+\s+days?|over \d+\s+days?)\b)/i
  );
  if (prepositionMatch?.[1]) {
    return prepositionMatch[1].trim().replace(/[.?!]+$/, "");
  }

  const fallback = normalized
    .replace(/[?.!,]/g, " ")
    .replace(
      /\b(?:what(?:'s| is)?|tell me|give me|show me|can you|please|current|weather|temperature|conditions|right now|currently|now)\b/gi,
      " "
    )
    .replace(/\s+/g, " ")
    .trim();

  return fallback || "Paris";
}

export class WeatherAgentExecutor implements AgentExecutor {
  public cancelTask = async (): Promise<void> => {};

  async execute(
    requestContext: RequestContext,
    eventBus: ExecutionEventBus
  ): Promise<void> {
    const userMessage = requestContext.userMessage;
    const existingTask = requestContext.task;
    const taskId = requestContext.taskId;
    const contextId = requestContext.contextId;

    if (!existingTask) {
      const initialTask: Task = {
        kind: "task",
        id: taskId,
        contextId,
        status: {
          state: "submitted",
          timestamp: new Date().toISOString(),
        },
        history: [userMessage],
        metadata: userMessage.metadata,
      };
      eventBus.publish(initialTask);
    }

    eventBus.publish({
      kind: "status-update",
      taskId,
      contextId,
      status: {
        state: "working",
        message: {
          kind: "message",
          role: "agent",
          messageId: uuidv4(),
          parts: [{ kind: "text", text: "Checking destination weather..." }],
          taskId,
          contextId,
        },
        timestamp: new Date().toISOString(),
      },
      final: false,
    } satisfies TaskStatusUpdateEvent);

    const userText = userMessage.parts
      .filter((part) => part.kind === "text")
      .map((part) => part.text)
      .join(" ")
      .trim();

    try {
      const city = extractCity(userText);
      if (wantsForecast(userText)) {
        const forecastDays = extractForecastDays(userText);
        const forecast = await getForecast(city, forecastDays);
        const responseText = forecast
          ? forecast
          : `I couldn't find forecast data for "${city}".`;

        eventBus.publish({
          kind: "status-update",
          taskId,
          contextId,
          status: {
            state: "completed",
            message: {
              kind: "message",
              role: "agent",
              messageId: uuidv4(),
              parts: [{ kind: "text", text: responseText }],
              taskId,
              contextId,
            },
            timestamp: new Date().toISOString(),
          },
          final: true,
        } satisfies TaskStatusUpdateEvent);
        return;
      }

      const weather = await getWeather(city);
      const responseText = weather
        ? `Current weather for ${weather.locationName}:\n` +
          `- Temperature: ${weather.temperature}°C\n` +
          `- Feels like: ${weather.apparentTemperature}°C\n` +
          `- Condition: ${weather.condition}\n` +
          `- Humidity: ${weather.humidity}%\n` +
          `- Wind Speed: ${weather.windSpeed} km/h\n` +
          `- Timezone: ${weather.timezone}`
        : `I couldn't find weather data for "${city}".`;

      eventBus.publish({
        kind: "status-update",
        taskId,
        contextId,
        status: {
          state: "completed",
          message: {
            kind: "message",
            role: "agent",
            messageId: uuidv4(),
            parts: [{ kind: "text", text: responseText }],
            taskId,
            contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      } satisfies TaskStatusUpdateEvent);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown weather lookup error";

      eventBus.publish({
        kind: "status-update",
        taskId,
        contextId,
        status: {
          state: "failed",
          message: {
            kind: "message",
            role: "agent",
            messageId: uuidv4(),
            parts: [{ kind: "text", text: `Weather lookup failed: ${message}` }],
            taskId,
            contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      } satisfies TaskStatusUpdateEvent);
    }
  }
}
