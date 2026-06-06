import { v4 as uuidv4 } from "uuid";
import { Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent } from "@a2a-js/sdk";
import {
  AgentExecutor,
  ExecutionEventBus,
  RequestContext,
} from "@a2a-js/sdk/server";
import { BookingRequest, createBookingConfirmation } from "./booking-service";

function readField(text: string, fieldName: string): string | null {
  const match = text.match(new RegExp(`^${fieldName}:\\s*(.*)$`, "im"));
  const value = match?.[1]?.trim() ?? "";
  return value || null;
}

function parseGuests(text: string): number | null {
  const raw = readField(text, "guests");
  if (!raw) {
    return null;
  }

  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseBookingRequest(text: string): BookingRequest {
  return {
    guestName: readField(text, "guest_name"),
    email: readField(text, "email"),
    creditCard: readField(text, "credit_card"),
    hotelName: readField(text, "hotel_name"),
    city: readField(text, "city"),
    checkInDate: readField(text, "check_in_date"),
    checkOutDate: readField(text, "check_out_date"),
    guests: parseGuests(text),
    roomType: readField(text, "room_type"),
    specialRequests: readField(text, "special_requests"),
  };
}

function buildConfirmationText(result: ReturnType<typeof createBookingConfirmation>): string {
  const cityPart = result.city ? ` in ${result.city}` : "";
  const requestNote = result.specialRequests
    ? ` Special requests: ${result.specialRequests}.`
    : "";

  return [
    `Hotel booking confirmed for ${result.guestName}.`,
    `Hotel: ${result.hotelName}${cityPart}.`,
    `Stay: ${result.checkInDate} to ${result.checkOutDate}.`,
    `Guests: ${result.guests}. Room type: ${result.roomType}.`,
    `Contact: ${result.email}. Payment: ${result.maskedCard}.`,
    `Confirmation code: ${result.confirmationCode}.${requestNote}`,
  ].join(" ");
}

export class HotelBookingAgentExecutor implements AgentExecutor {
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
          parts: [{ kind: "text", text: "Creating hotel booking..." }],
          taskId,
          contextId,
        },
        timestamp: new Date().toISOString(),
      },
      final: false,
    } satisfies TaskStatusUpdateEvent);

    try {
      const userText = userMessage.parts
        .filter((part) => part.kind === "text")
        .map((part) => part.text)
        .join(" ")
        .trim();

      const bookingRequest = parseBookingRequest(userText);
      const confirmation = createBookingConfirmation(bookingRequest);

      eventBus.publish({
        kind: "artifact-update",
        taskId,
        contextId,
        artifact: {
          artifactId: uuidv4(),
          name: "hotel-booking-confirmation",
          description: "Structured hotel booking confirmation",
          parts: [{ kind: "data", data: confirmation }],
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
            parts: [{ kind: "text", text: buildConfirmationText(confirmation) }],
            taskId,
            contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      } satisfies TaskStatusUpdateEvent);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown hotel booking error";

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
            parts: [{ kind: "text", text: `Hotel booking failed: ${message}` }],
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
