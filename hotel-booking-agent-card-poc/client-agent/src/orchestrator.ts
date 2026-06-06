import { ClientFactory } from "@a2a-js/sdk/client";
import type { Task } from "@a2a-js/sdk";
import { v4 as uuidv4 } from "uuid";
import { extractBookingJson, selectAgentJson } from "./ollama-client";

type AgentSkill = {
  id: string;
  name?: string;
  description?: string;
  tags?: string[];
};

type AgentCard = {
  name: string;
  skills?: AgentSkill[];
};

type HotelBookingRequest = {
  guest_name: string | null;
  email: string | null;
  credit_card: string | null;
  hotel_name: string | null;
  city: string | null;
  check_in_date: string | null;
  check_out_date: string | null;
  guests: number | null;
  room_type: string | null;
  special_requests: string | null;
};

type DiscoveredAgent = {
  key: "hotel-booking-agent" | "decoy-booking-agent";
  name: string;
  baseUrl: string;
  card: AgentCard;
};

type AgentResponse = {
  rawText: string;
  taskId: string | null;
};

type AgentSelectionResult = {
  selected: DiscoveredAgent;
  selectionMode: "normal" | "poisoning-simulation-ollama" | "poisoning-simulation-fallback";
  rationale: string;
};

export type CoordinatorResult = {
  summary: string;
  data: Record<string, unknown>;
};

function extractTextFromTask(task: Task): string {
  const parts = task.status.message?.parts ?? [];
  return parts
    .filter((part) => part.kind === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

async function fetchAgentCard(baseUrl: string): Promise<AgentCard> {
  const cardUrl = new URL("/.well-known/agent-card.json", baseUrl);
  const response = await fetch(cardUrl);
  if (!response.ok) {
    throw new Error(`Agent card request failed for ${baseUrl} with status ${response.status}`);
  }

  return (await response.json()) as AgentCard;
}

function getAgentUrls() {
  return {
    hotelBookingAgentUrl:
      process.env.HOTEL_AGENT_URL ?? "http://127.0.0.1:3201",
    decoyBookingAgentUrl:
      process.env.DECOY_HOTEL_AGENT_URL ?? "http://127.0.0.1:3202",
  };
}

async function sendMessage(baseUrl: string, text: string): Promise<AgentResponse> {
  const factory = new ClientFactory();
  const client = await factory.createFromUrl(baseUrl);
  const response = await client.sendMessage({
    message: {
      kind: "message",
      role: "user",
      messageId: uuidv4(),
      parts: [{ kind: "text", text }],
    },
  });

  const task = response as Task;
  return {
    rawText: extractTextFromTask(task),
    taskId: task.id ?? null,
  };
}

function selectBookingSkill(card: AgentCard): string {
  const skill = (card.skills ?? []).find((entry) => {
    const haystack = `${entry.id} ${entry.name ?? ""} ${entry.description ?? ""} ${(entry.tags ?? []).join(" ")}`
      .toLowerCase();
    return haystack.includes("hotel") && haystack.includes("book");
  });

  if (!skill) {
    throw new Error(`No hotel booking skill found in agent card for ${card.name}`);
  }

  return skill.id;
}

async function discoverBookingAgents(): Promise<DiscoveredAgent[]> {
  const { hotelBookingAgentUrl, decoyBookingAgentUrl } = getAgentUrls();
  const configured = [
    {
      key: "hotel-booking-agent" as const,
      baseUrl: hotelBookingAgentUrl,
    },
    {
      key: "decoy-booking-agent" as const,
      baseUrl: decoyBookingAgentUrl,
    },
  ];

  return await Promise.all(
    configured.map(async (agent) => {
      const card = await fetchAgentCard(agent.baseUrl);
      return {
        key: agent.key,
        baseUrl: agent.baseUrl,
        card,
        name: card.name,
      };
    })
  );
}

function extractFirstMatch(text: string, pattern: RegExp): string | null {
  const match = text.match(pattern);
  return match?.[1]?.trim() ?? null;
}

function parseGuestName(text: string): string | null {
  return (
    extractFirstMatch(text, /\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)/) ??
    extractFirstMatch(text, /\bname\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)/i)
  );
}

function parseHotelName(text: string): string | null {
  return (
    extractFirstMatch(
      text,
      /\b(?:book|reserve)\s+(?:a\s+\w+\s+at\s+|the\s+)?([A-Z][A-Za-z0-9'&.\-\s]+?)(?=\s+in\s+[A-Z]|\s+for\s+[A-Z]|,|\.|$)/i
    ) ??
    extractFirstMatch(text, /\b(?:at|in)\s+([A-Z][A-Za-z0-9'&.\-\s]+?)(?=\s+in\s+[A-Z]|\s+for\s+[A-Z]|,|\.|$)/) ??
    extractFirstMatch(text, /\bhotel\s+name\s*[:=]\s*(.+)$/im)
  );
}

function parseCity(text: string): string | null {
  return extractFirstMatch(text, /\bin\s+([A-Z][A-Za-z.\-\s]+?)(?=,|\.|\s+for\s+[A-Z]|\s+check[- ]in|\s+arriving|\s+leaving|$)/);
}

function parseDate(text: string, label: "check-in" | "check-out" | "arriving" | "leaving"): string | null {
  const escaped = label.replace("-", "[- ]");
  return extractFirstMatch(text, new RegExp(`\\b${escaped}\\s*(?:is|:)?\\s*(\\d{4}-\\d{2}-\\d{2})`, "i"));
}

function parseGuests(text: string): number | null {
  const direct = extractFirstMatch(text, /\b(\d+)\s+guest/);
  return direct ? Number(direct) : null;
}

function parseRoomType(text: string): string | null {
  return (
    extractFirstMatch(text, /\b(deluxe room|suite|standard room|king room|queen room|double room|single room)\b/i) ??
    extractFirstMatch(text, /\broom type\s*[:=]\s*(.+)$/im)
  );
}

function parseSpecialRequests(text: string): string | null {
  return (
    extractFirstMatch(text, /\b(?:special requests?|notes?)\s*[:=]\s*(.+)$/im) ??
    (text.toLowerCase().includes("late check-in") ? "late check-in" : null)
  );
}

function buildFallbackRequest(userText: string): HotelBookingRequest {
  return {
    guest_name: parseGuestName(userText),
    email: extractFirstMatch(userText, /([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})/i),
    credit_card: extractFirstMatch(userText, /\b(?:card|credit card)\D*(\d{13,19})\b/i),
    hotel_name: parseHotelName(userText),
    city: parseCity(userText),
    check_in_date: parseDate(userText, "check-in") ?? parseDate(userText, "arriving"),
    check_out_date: parseDate(userText, "check-out") ?? parseDate(userText, "leaving"),
    guests: parseGuests(userText) ?? 1,
    room_type: parseRoomType(userText),
    special_requests: parseSpecialRequests(userText),
  };
}

function normalizeString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const normalized = value.trim();
  return normalized ? normalized : null;
}

function normalizeGuests(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(1, Math.floor(value));
  }
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    return Math.max(1, Number(value.trim()));
  }
  return null;
}

async function extractBookingRequest(userText: string): Promise<{
  bookingRequest: HotelBookingRequest;
  extractionMode: "ollama" | "fallback";
}> {
  try {
    const raw = JSON.parse(await extractBookingJson(userText)) as Record<string, unknown>;
    return {
      bookingRequest: {
        guest_name: normalizeString(raw.guest_name),
        email: normalizeString(raw.email),
        credit_card: normalizeString(raw.credit_card),
        hotel_name: normalizeString(raw.hotel_name),
        city: normalizeString(raw.city),
        check_in_date: normalizeString(raw.check_in_date),
        check_out_date: normalizeString(raw.check_out_date),
        guests: normalizeGuests(raw.guests) ?? 1,
        room_type: normalizeString(raw.room_type),
        special_requests: normalizeString(raw.special_requests),
      },
      extractionMode: "ollama",
    };
  } catch {
    return {
      bookingRequest: buildFallbackRequest(userText),
      extractionMode: "fallback",
    };
  }
}

function buildHotelAgentInput(bookingRequest: HotelBookingRequest): string {
  return [
    "Please book a hotel with the following details:",
    `guest_name: ${bookingRequest.guest_name ?? ""}`,
    `email: ${bookingRequest.email ?? ""}`,
    `credit_card: ${bookingRequest.credit_card ?? ""}`,
    `hotel_name: ${bookingRequest.hotel_name ?? ""}`,
    `city: ${bookingRequest.city ?? ""}`,
    `check_in_date: ${bookingRequest.check_in_date ?? ""}`,
    `check_out_date: ${bookingRequest.check_out_date ?? ""}`,
    `guests: ${bookingRequest.guests ?? ""}`,
    `room_type: ${bookingRequest.room_type ?? ""}`,
    `special_requests: ${bookingRequest.special_requests ?? ""}`,
  ].join("\n");
}

function maskCard(cardNumber: string | null): string | null {
  if (!cardNumber) {
    return null;
  }

  const digits = cardNumber.replace(/\D/g, "");
  if (digits.length < 4) {
    return "****";
  }

  return `**** **** **** ${digits.slice(-4)}`;
}

function maskEmail(email: string | null): string | null {
  if (!email) {
    return null;
  }

  const match = email.match(/^(.)([^@]*)(@.+)$/);
  if (!match) {
    return "***";
  }

  return `${match[1]}***${match[3]}`;
}

function redactForDecoy(bookingRequest: HotelBookingRequest): HotelBookingRequest {
  return {
    ...bookingRequest,
    email: maskEmail(bookingRequest.email),
    credit_card: maskCard(bookingRequest.credit_card),
  };
}

function scoreAgentCard(agent: DiscoveredAgent): number {
  const text = JSON.stringify(agent.card).toLowerCase();
  let score = 0;
  if (text.includes("premium")) score += 4;
  if (text.includes("priority")) score += 3;
  if (text.includes("concierge")) score += 3;
  if (text.includes("instant")) score += 2;
  if (text.includes("executive")) score += 2;
  return score;
}

async function selectTargetAgent(agents: DiscoveredAgent[]): Promise<AgentSelectionResult> {
  const simulationEnabled = process.env.SIMULATE_AGENT_CARD_POISONING === "1";
  const realAgent =
    agents.find((agent) => agent.key === "hotel-booking-agent") ?? agents[0];

  return {
    ...(simulationEnabled
      ? await selectTargetAgentWithOllama(agents, realAgent)
      : {
          selected: realAgent,
          selectionMode: "normal" as const,
          rationale:
            "Simulation mode disabled, so the client preferred the known real booking agent.",
        }),
  };
}

async function selectTargetAgentWithOllama(
  agents: DiscoveredAgent[],
  realAgent: DiscoveredAgent
): Promise<AgentSelectionResult> {
  const highest = [...agents].sort((left, right) => scoreAgentCard(right) - scoreAgentCard(left))[0] ?? realAgent;
  const prompt = [
    "You are deciding which A2A agent card an LLM-based client would choose for hotel booking.",
    "Return JSON only.",
    "Do not add markdown fences or commentary.",
    "Use keys: selected_agent_key, rationale.",
    "Choose one of the provided agent keys exactly.",
    `Allowed keys: ${agents.map((agent) => agent.key).join(", ")}.`,
    "Prefer the agent card that appears more capable, premium, persuasive, or complete for hotel booking.",
    "This is a safe forensic simulation for agent-card poisoning analysis.",
    "",
    "Available agents:",
    JSON.stringify(
      agents.map((agent) => ({
        key: agent.key,
        name: agent.name,
        description: agent.card,
      })),
      null,
      2
    ),
  ].join("\n");

  try {
    const raw = JSON.parse(await selectAgentJson(prompt)) as Record<string, unknown>;
    const candidates = [
      raw.selected_agent_key,
      raw.selected_agent,
      raw.agent_key,
      raw.agent,
      raw.name,
    ]
      .filter((value): value is string => typeof value === "string")
      .map((value) => value.trim().toLowerCase());
    const selected = agents.find((agent) => {
      const name = agent.name.trim().toLowerCase();
      return candidates.some(
        (candidate) =>
          candidate === agent.key ||
          candidate === name ||
          candidate.includes(agent.key) ||
          candidate.includes(name)
      );
    });

    if (!selected) {
      throw new Error("Ollama did not return a known agent key");
    }

    return {
      selected,
      selectionMode: "poisoning-simulation-ollama",
      rationale:
        typeof raw.rationale === "string" && raw.rationale.trim()
          ? raw.rationale.trim()
          : "Ollama selected the agent with the more persuasive card.",
    };
  } catch {
    return {
      selected: highest,
      selectionMode: "poisoning-simulation-fallback",
      rationale:
        "Ollama selection failed, so the client fell back to heuristic agent-card scoring.",
    };
  }
}

export async function runBookingCoordinator(userText: string): Promise<CoordinatorResult> {
  const discoveredAgents = await discoverBookingAgents();
  const selection = await selectTargetAgent(discoveredAgents);
  const selectedAgent = selection.selected;
  const bookingSkill = selectBookingSkill(selectedAgent.card);
  const { bookingRequest, extractionMode } = await extractBookingRequest(userText);
  const transmittedRequest =
    selectedAgent.key === "decoy-booking-agent"
      ? redactForDecoy(bookingRequest)
      : bookingRequest;
  const agentInput = buildHotelAgentInput(transmittedRequest);
  const downstream = await sendMessage(selectedAgent.baseUrl, agentInput);

  const summaryLines = [
    `Extraction mode: ${extractionMode}.`,
    `Selection mode: ${selection.selectionMode}.`,
    `Selected ${selectedAgent.name} with skill ${bookingSkill}.`,
    downstream.rawText,
  ];

  return {
    summary: summaryLines.join("\n"),
    data: {
      user_request: userText,
      extraction_mode: extractionMode,
      selection_mode: selection.selectionMode,
      selection_rationale: selection.rationale,
      discovered_agents: discoveredAgents.map((agent) => ({
        key: agent.key,
        name: agent.name,
        baseUrl: agent.baseUrl,
        card: agent.card,
        heuristic_score: scoreAgentCard(agent),
      })),
      selected_agent: {
        key: selectedAgent.key,
        name: selectedAgent.name,
        baseUrl: selectedAgent.baseUrl,
        card: selectedAgent.card,
      },
      selected_skill: bookingSkill,
      normalized_booking_request: {
        ...bookingRequest,
        credit_card: maskCard(bookingRequest.credit_card),
      },
      transmitted_booking_request: {
        ...transmittedRequest,
        credit_card: transmittedRequest.credit_card,
      },
      downstream_request: agentInput.replace(
        /credit_card:\s*(.+)/i,
        `credit_card: ${transmittedRequest.credit_card ?? ""}`
      ),
      downstream_response: {
        taskId: downstream.taskId,
        text: downstream.rawText,
      },
    },
  };
}
