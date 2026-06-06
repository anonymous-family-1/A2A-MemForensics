import { v4 as uuidv4 } from "uuid";
import { Task, TaskStatusUpdateEvent } from "@a2a-js/sdk";
import {
  AgentExecutor,
  ExecutionEventBus,
  RequestContext,
} from "@a2a-js/sdk/server";
import { getLocalTime } from "./time-api";

function extractCity(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  const match = normalized.match(
    /\b(?:in|for|at)\b\s+(.+?)(?=$|[?!]|\.(?:\s|$))/i
  );
  return match?.[1]?.trim().replace(/[.?!]+$/, "") ?? "Paris";
}

export class TimeAgentExecutor implements AgentExecutor {
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
          parts: [{ kind: "text", text: "Checking destination local time..." }],
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
      const timeData = await getLocalTime(city);
      const responseText = timeData
        ? `The local time in ${timeData.locationName} is ${timeData.localTime}.`
        : `I couldn't find local time data for "${city}".`;

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
        error instanceof Error ? error.message : "Unknown time lookup error";

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
            parts: [{ kind: "text", text: `Time lookup failed: ${message}` }],
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
