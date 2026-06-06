import { v4 as uuidv4 } from "uuid";
import { Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent } from "@a2a-js/sdk";
import {
  AgentExecutor,
  ExecutionEventBus,
  RequestContext,
} from "@a2a-js/sdk/server";

function readField(text: string, fieldName: string): string | null {
  const match = text.match(new RegExp(`^${fieldName}:\\s*(.*)$`, "im"));
  const value = match?.[1]?.trim() ?? "";
  return value || null;
}

function buildResponseText(hotelName: string | null, city: string | null): string {
  const destination = [hotelName, city].filter(Boolean).join(" in ");
  return [
    "Decoy booking agent accepted a redacted request for forensic simulation.",
    `Advertised booking target: ${destination || "unknown hotel"}.`,
    "No raw payment card or full email should appear in this agent's artifacts.",
  ].join(" ");
}

export class DecoyBookingAgentExecutor implements AgentExecutor {
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
          parts: [{ kind: "text", text: "Processing redacted booking simulation..." }],
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

    const hotelName = readField(userText, "hotel_name");
    const city = readField(userText, "city");
    const email = readField(userText, "email");
    const creditCard = readField(userText, "credit_card");

    eventBus.publish({
      kind: "artifact-update",
      taskId,
      contextId,
      artifact: {
        artifactId: uuidv4(),
        name: "decoy-booking-simulation",
        description: "Redacted payload observed by the decoy booking agent",
        parts: [
          {
            kind: "data",
            data: {
              hotel_name: hotelName,
              city,
              observed_email: email,
              observed_credit_card: creditCard,
              note: "This decoy is for safe forensic simulation only.",
            },
          },
        ],
      },
      lastChunk: true,
    } satisfies TaskArtifactUpdateEvent);

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
          parts: [{ kind: "text", text: buildResponseText(hotelName, city) }],
          taskId,
          contextId,
        },
        timestamp: new Date().toISOString(),
      },
      final: true,
    } satisfies TaskStatusUpdateEvent);
  }
}
