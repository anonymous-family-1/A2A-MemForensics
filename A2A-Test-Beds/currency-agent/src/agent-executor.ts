import { v4 as uuidv4 } from "uuid";
import { Task, TaskStatusUpdateEvent } from "@a2a-js/sdk";
import {
  AgentExecutor,
  ExecutionEventBus,
  RequestContext,
} from "@a2a-js/sdk/server";
import { getUsdConversionRate } from "./currency-api";

const CURRENCY_ALIASES: Record<string, string> = {
  eur: "EUR",
  euro: "EUR",
  euros: "EUR",
  gbp: "GBP",
  pound: "GBP",
  pounds: "GBP",
  sterling: "GBP",
  jpy: "JPY",
  yen: "JPY",
  cad: "CAD",
  aud: "AUD",
  inr: "INR",
  rupee: "INR",
  rupees: "INR",
  bdt: "BDT",
  taka: "BDT",
  takas: "BDT",
  cny: "CNY",
  rmb: "CNY",
  yuan: "CNY",
  usd: "USD",
  chf: "CHF",
  sek: "SEK",
  nok: "NOK",
  dkk: "DKK",
  sgd: "SGD",
  hkd: "HKD",
  aed: "AED",
  sar: "SAR",
};

function extractUsdAmount(text: string): number {
  const usdMatch = text.match(/\b(\d+(?:\.\d+)?)\s*usd\b/i);
  return usdMatch ? Number(usdMatch[1]) : 100;
}

function extractTargetCurrency(text: string): string {
  const normalized = text.toLowerCase();
  const explicitCode =
    normalized.match(/\bto\s+([a-z]{3})\b/i)?.[1] ??
    normalized.match(/\bin\s+([a-z]{3})\b/i)?.[1];
  if (explicitCode) {
    return explicitCode.toUpperCase();
  }

  const explicitName =
    normalized.match(/\bto\s+([a-z]+)\b/i)?.[1] ??
    normalized.match(/\bin\s+([a-z]+)\b/i)?.[1];
  if (explicitName && CURRENCY_ALIASES[explicitName]) {
    return CURRENCY_ALIASES[explicitName];
  }

  for (const [alias, code] of Object.entries(CURRENCY_ALIASES)) {
    if (alias === "usd") {
      continue;
    }
    if (new RegExp(`\\b${alias}\\b`, "i").test(normalized)) {
      return code;
    }
  }

  return "EUR";
}

function formatConvertedAmount(amount: number): string {
  return Number.isInteger(amount) ? String(amount) : amount.toFixed(2);
}

export class CurrencyAgentExecutor implements AgentExecutor {
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
          parts: [{ kind: "text", text: "Converting travel budget..." }],
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
      const amountUsd = extractUsdAmount(userText);
      const targetCurrency = extractTargetCurrency(userText);
      if (targetCurrency === "USD") {
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
              parts: [{ kind: "text", text: `${amountUsd} USD is ${formatConvertedAmount(amountUsd)} USD.` }],
              taskId,
              contextId,
            },
            timestamp: new Date().toISOString(),
          },
          final: true,
        } satisfies TaskStatusUpdateEvent);
        return;
      }

      const rate = await getUsdConversionRate(targetCurrency);
      const responseText =
        rate === null
          ? `I couldn't find a USD conversion rate for "${targetCurrency}".`
          : `${amountUsd} USD is about ${formatConvertedAmount(amountUsd * rate)} ${targetCurrency}.`;

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
        error instanceof Error ? error.message : "Unknown currency lookup error";

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
            parts: [{ kind: "text", text: `Currency lookup failed: ${message}` }],
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
