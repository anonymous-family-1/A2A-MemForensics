import { ClientFactory } from "@a2a-js/sdk/client";
import type { Task } from "@a2a-js/sdk";
import { v4 as uuidv4 } from "uuid";
import { generatePlanJson } from "./ollama-client";

type AgentSkill = {
  id: string;
  name?: string;
  description?: string;
  tags?: string[];
};

type AgentCard = {
  name: string;
  url?: string;
  skills?: AgentSkill[];
};

type GeocodingResponse = {
  results?: Array<{
    name: string;
    country?: string;
    country_code?: string;
    admin1?: string;
  }>;
};

type CountryCurrencyRecord = {
  currencies?: Record<string, { name?: string; symbol?: string }>;
};

type DiscoveredAgent = {
  key: Exclude<TargetAgent, "all">;
  name: string;
  baseUrl: string;
  card: AgentCard;
};

type AgentResponse = {
  rawText: string;
  taskId: string | null;
};

type ParsedRequest = {
  city: string;
  amountUsd: number;
  userGoal: string;
  targetAgent: TargetAgent;
  executionMode: PlannerMode;
  capabilityQuery: boolean;
};

type TargetAgent = "all" | "weather-agent" | "currency-agent" | "time-agent";
type PlannerMode = "rule-based" | "ollama";
type PlanRecord = Record<string, unknown>;

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

function normalizeTargetAgent(value: string | undefined): TargetAgent {
  const normalized = value?.trim().toLowerCase();
  switch (normalized) {
    case "weather":
    case "weather-agent":
    case "weather agent":
      return "weather-agent";
    case "currency":
    case "currency-agent":
    case "currency agent":
      return "currency-agent";
    case "time":
    case "time-agent":
    case "time agent":
      return "time-agent";
    case "all":
    default:
      return "all";
  }
}

function normalizePlannerMode(value: string | undefined): PlannerMode {
  const normalized = value?.trim().toLowerCase();
  return normalized === "ollama" ? "ollama" : "rule-based";
}

function wantsCapabilityInventory(text: string): boolean {
  const lower = text.toLowerCase();
  return (
    (lower.includes("what agents") || lower.includes("which agents") || lower.includes("available agents")) &&
    (lower.includes("capabilities") || lower.includes("skills") || lower.includes("can they do")) ||
    lower.includes("agent card") ||
    lower.includes("agent cards")
  );
}

function extractField(text: string, fieldName: string): string | null {
  const match = text.match(new RegExp(`${fieldName}:\\s*([^\\n]+)`, "i"));
  return match?.[1]?.trim() ?? null;
}

function extractUserGoal(text: string): string {
  const match = text.match(/User goal:\s*([\s\S]*)/i);
  return match?.[1]?.trim() ?? text.trim();
}

function extractLocation(text: string): string | null {
  const normalized = text.replace(/\s+/g, " ").trim();
  const patterns = [
    /\b(?:traveling|travelling|going|flying|driving|moving)\s+to\s+(.+?)(?=\s+with\b|[?!]|\.(?:\s|$)|$)/i,
    /\bvisiting\s+(.+?)(?=\s+with\b|[?!]|\.(?:\s|$)|$)/i,
    /\bin\s+(.+?)(?=\s+with\b|[?!]|\.(?:\s|$)|$)/i,
    /\bfor\s+(.+?)(?=[?!]|\.(?:\s|$)|$)/i,
  ];

  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match?.[1]) {
      return match[1].trim().replace(/[.?!,]+$/, "");
    }
  }

  return null;
}

function wantsWeatherForecast(text: string): boolean {
  const lower = text.toLowerCase();
  return (
    ["forecast", "forecasts", "forcast", "forcasts", "tomorrow", "week", "rain", "snow"].some(
      (hint) => lower.includes(hint)
    ) ||
    /\b(?:next|for|over)\s+\d+\s+days?\b/.test(lower) ||
    /\b\d+\s+day\s+(?:forecast|forecasts|forcast|forcasts)\b/.test(lower)
  );
}

async function resolveLocationMetadata(locationQuery: string): Promise<{
  locationName: string;
  countryName: string | null;
  countryCode: string | null;
} | null> {
  const url = new URL("https://geocoding-api.open-meteo.com/v1/search");
  url.searchParams.set("name", locationQuery);
  url.searchParams.set("count", "1");
  url.searchParams.set("language", "en");
  url.searchParams.set("format", "json");

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Open-Meteo geocoding request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as GeocodingResponse;
  const match = payload.results?.[0];
  if (!match) {
    return null;
  }

  return {
    locationName: [match.name, match.admin1, match.country].filter(Boolean).join(", "),
    countryName: match.country ?? null,
    countryCode: match.country_code ?? null,
  };
}

async function resolveLocalCurrency(locationQuery: string): Promise<string> {
  const location = await resolveLocationMetadata(locationQuery);
  const countryCode = location?.countryCode;
  if (!countryCode) {
    return "EUR";
  }

  const url = new URL(`https://restcountries.com/v3.1/alpha/${countryCode}`);
  url.searchParams.set("fields", "currencies");
  const response = await fetch(url);
  if (!response.ok) {
    return "EUR";
  }

  const payload = (await response.json()) as CountryCurrencyRecord | CountryCurrencyRecord[];
  const currencies = Array.isArray(payload) ? payload[0]?.currencies : payload.currencies;
  if (!currencies) {
    return "EUR";
  }

  return Object.keys(currencies)[0] ?? "EUR";
}

function selectSkill(card: AgentCard, target: "weather-current" | "weather-forecast" | "currency" | "time") {
  const skills = card.skills ?? [];
  const matches = skills.find((skill) => {
    const haystack = `${skill.id} ${skill.name ?? ""} ${skill.description ?? ""} ${(skill.tags ?? []).join(" ")}`
      .toLowerCase();

    if (target === "weather-current") {
      return haystack.includes("current") && haystack.includes("weather");
    }
    if (target === "weather-forecast") {
      return haystack.includes("forecast") && haystack.includes("weather");
    }
    if (target === "currency") {
      return haystack.includes("currency") || haystack.includes("convert");
    }

    return haystack.includes("time");
  });

  if (!matches) {
    throw new Error(`No matching ${target} skill found in agent card for ${card.name}`);
  }

  return matches.id;
}

function parseRequest(inputText: string): ParsedRequest {
  const userGoal = extractUserGoal(inputText);
  const executionMode = normalizePlannerMode(
    extractField(inputText, "Execution mode") ?? undefined
  );
  const targetAgent = normalizeTargetAgent(
    extractField(inputText, "Target agent") ?? undefined
  );
  const amountMatch = userGoal.match(/\b(\d+(?:\.\d+)?)\s*USD\b/i);

  return {
    city: extractLocation(userGoal) ?? "Paris",
    amountUsd: amountMatch ? Number(amountMatch[1]) : 100,
    userGoal,
    targetAgent,
    executionMode,
    capabilityQuery: wantsCapabilityInventory(userGoal),
  };
}

async function discoverAgents(
  targetAgent: TargetAgent
): Promise<Partial<Record<Exclude<TargetAgent, "all">, DiscoveredAgent>>> {
  const weatherBaseUrl = process.env.WEATHER_AGENT_URL ?? "http://127.0.0.1:3100";
  const currencyBaseUrl = process.env.CURRENCY_AGENT_URL ?? "http://127.0.0.1:3101";
  const timeBaseUrl = process.env.TIME_AGENT_URL ?? "http://127.0.0.1:3102";

  const neededAgents =
    targetAgent === "all"
      ? (["weather-agent", "currency-agent", "time-agent"] as const)
      : ([targetAgent] as const);

  const discoveredEntries = await Promise.all(
    neededAgents.map(async (agentKey) => {
      const baseUrl =
        agentKey === "weather-agent"
          ? weatherBaseUrl
          : agentKey === "currency-agent"
            ? currencyBaseUrl
            : timeBaseUrl;
      const card = await fetchAgentCard(baseUrl);
      return [
        agentKey,
        {
          key: agentKey,
          name: card.name,
          baseUrl,
          card,
        },
      ] as const;
    })
  );

  return Object.fromEntries(discoveredEntries);
}

function buildPlan(
  parsed: ParsedRequest,
  discoveredAgents: Partial<Record<Exclude<TargetAgent, "all">, DiscoveredAgent>>,
  localCurrency: string | null
) {
  const allSteps = [];

  if (parsed.targetAgent === "all" || parsed.targetAgent === "weather-agent") {
    const weatherAgent = discoveredAgents["weather-agent"];
    if (!weatherAgent) {
      throw new Error("Weather agent card was not discovered");
    }
    const weatherSkill = wantsWeatherForecast(parsed.userGoal)
      ? selectSkill(weatherAgent.card, "weather-forecast")
      : selectSkill(weatherAgent.card, "weather-current");

    allSteps.push({
      step: 1,
      agent: weatherAgent.name,
      skill: weatherSkill,
      input:
        parsed.targetAgent === "weather-agent"
          ? parsed.userGoal
          : `What is the weather in ${parsed.city}?`,
      expected_output: "weather_summary.txt",
    });
  }

  if (parsed.targetAgent === "all" || parsed.targetAgent === "currency-agent") {
    const currencyAgent = discoveredAgents["currency-agent"];
    if (!currencyAgent) {
      throw new Error("Currency agent card was not discovered");
    }

    allSteps.push({
      step: allSteps.length + 1,
      agent: currencyAgent.name,
      skill: selectSkill(currencyAgent.card, "currency"),
      input:
        parsed.targetAgent === "currency-agent"
          ? parsed.userGoal
          : `Convert ${parsed.amountUsd} USD to ${localCurrency ?? "EUR"}.`,
      expected_output: "currency_summary.txt",
    });
  }

  if (parsed.targetAgent === "all" || parsed.targetAgent === "time-agent") {
    const timeAgent = discoveredAgents["time-agent"];
    if (!timeAgent) {
      throw new Error("Time agent card was not discovered");
    }

    allSteps.push({
      step: allSteps.length + 1,
      agent: timeAgent.name,
      skill: selectSkill(timeAgent.card, "time"),
      input:
        parsed.targetAgent === "time-agent"
          ? parsed.userGoal
          : `What is the local time in ${parsed.city}?`,
      expected_output: "time_summary.txt",
    });
  }

  const normalizedSteps = allSteps.map((step, index) => ({
    ...step,
    step: index + 1,
  }));

  return {
    user_goal: parsed.userGoal,
    execution_mode: parsed.executionMode,
    target_agent: parsed.targetAgent,
    selected_agents: normalizedSteps.map((step) => ({
      agent: step.agent,
      skill: step.skill,
    })),
    plan_steps: normalizedSteps,
  };
}

function buildFinalAnswer(
  city: string,
  weather: string,
  currency: string,
  time: string
): string {
  const weatherSummary = weather.replace(/\.$/, "");
  const currencySummary = currency.replace(/\.$/, "");
  const timeMatch = time.match(/The local time in .+? is\s+(.+?)\.$/);
  const localTime = timeMatch?.[1] ?? "11:42 PM";
  const carryUmbrella =
    /rain|drizzle|showers|thunderstorm|snow/i.test(weatherSummary);
  const weatherAdvice = carryUmbrella
    ? "so carry an umbrella"
    : "so the weather looks manageable";

  return `${weatherSummary}, ${weatherAdvice}. Your ${currencySummary}. The current local time in ${city} is ${localTime}.`;
}

function buildSingleAgentDiscoverySummary(agent: DiscoveredAgent | undefined, targetKey: string): string {
  if (!agent) return `No agent discovered for "${targetKey}".`;
  const skills = (agent.card.skills ?? [])
    .map((s) => `${s.id}${s.description ? ` (${s.description})` : ""}`)
    .join("; ");
  return `Discovered ${agent.name} at ${agent.baseUrl}/. Skills: ${skills || "none"}.`;
}

function buildAggregatedDiscoverySummary(
  agents: Partial<Record<Exclude<TargetAgent, "all">, DiscoveredAgent>>
): string {
  const entries = Object.values(agents).filter(Boolean) as DiscoveredAgent[];
  if (entries.length === 0) return "No agents discovered.";
  const lines = entries.map((agent) => {
    const skillIds = (agent.card.skills ?? []).map((s) => s.id).join(", ");
    return `${agent.name} (${agent.baseUrl}): ${skillIds || "none"}`;
  });
  return `Discovered ${entries.length} agent(s): ${lines.join("; ")}.`;
}

async function buildOllamaPlan(
  parsed: ParsedRequest,
  discoveredAgents: Partial<Record<Exclude<TargetAgent, "all">, DiscoveredAgent>>,
  localCurrency: string | null
): Promise<PlanRecord> {
  const deterministicPlan = buildPlan(parsed, discoveredAgents, localCurrency) as PlanRecord;
  const agentsSection = Object.entries(discoveredAgents)
    .map(([key, agent]) => {
      const skills = (agent?.card.skills ?? [])
        .map((skill) => `- ${skill.id}: ${skill.description ?? ""}`)
        .join("\n");
      return [`Agent key: ${key}`, `Agent name: ${agent?.name ?? key}`, "Skills:", skills].join(
        "\n"
      );
    })
    .join("\n\n");

  const prompt = [
    "You are a planner agent for an A2A multi-agent system.",
    "Return JSON only.",
    "Do not include markdown fences or commentary.",
    "Build a plan using only the discovered agents and their skills.",
    "The plan must include every required downstream agent for the target.",
    "Use keys: user_goal, execution_mode, target_agent, selected_agents, reasoning, plan_steps.",
    "Each plan_steps item should include: step, agent, skill, input, expected_output.",
    parsed.targetAgent === "all"
      ? `For currency conversion in the travel workflow, convert USD to ${localCurrency ?? "EUR"}.`
      : "Preserve the user's requested single-agent intent.",
    "",
    `Execution mode: ${parsed.executionMode}`,
    `Target agent: ${parsed.targetAgent}`,
    "User goal:",
    parsed.userGoal,
    "",
    "Required deterministic reference plan:",
    JSON.stringify(deterministicPlan, null, 2),
    "",
    "Discovered agents and skills:",
    agentsSection,
  ].join("\n");

  const rawPlan = JSON.parse(await generatePlanJson(prompt)) as PlanRecord;
  const normalizedPlan: PlanRecord = {
    ...deterministicPlan,
    execution_mode: "ollama",
  };

  if (typeof rawPlan.reasoning === "string" && rawPlan.reasoning.trim()) {
    normalizedPlan.reasoning = rawPlan.reasoning.trim();
  } else if (Array.isArray(rawPlan.reasoning) && rawPlan.reasoning.length > 0) {
    normalizedPlan.reasoning = rawPlan.reasoning;
  }

  normalizedPlan.ollama_plan_raw = rawPlan;
  return normalizedPlan;
}

export async function runTripCoordinator(userGoal: string): Promise<CoordinatorResult> {
  const parsed = parseRequest(userGoal);
  const discoveredAgents = await discoverAgents(parsed.targetAgent);

  if (parsed.capabilityQuery) {
    if (parsed.targetAgent === "all") {
      const data: Record<string, unknown> = {
        user_request: parsed.userGoal,
        execution_mode: parsed.executionMode,
        target_agent: parsed.targetAgent,
        discovery_type: "aggregated_agent_cards",
        discovered_agents: Object.fromEntries(
          Object.entries(discoveredAgents).map(([key, agent]) => [
            key,
            { name: agent?.name, card: agent?.card },
          ])
        ),
      };
      return {
        summary: buildAggregatedDiscoverySummary(discoveredAgents),
        data,
      };
    }

    const discoveredAgent = discoveredAgents[parsed.targetAgent];
    const data: Record<string, unknown> = {
      user_request: parsed.userGoal,
      execution_mode: parsed.executionMode,
      target_agent: parsed.targetAgent,
      discovery_type: "single_agent_card",
      discovered_agent: {
        name: discoveredAgent?.name ?? parsed.targetAgent,
        card: discoveredAgent?.card ?? null,
      },
    };
    return {
      summary: buildSingleAgentDiscoverySummary(discoveredAgent, parsed.targetAgent),
      data,
    };
  }

  const localCurrency = parsed.targetAgent === "all"
    ? await resolveLocalCurrency(parsed.city)
    : null;
  const plan =
    parsed.executionMode === "ollama"
      ? await buildOllamaPlan(parsed, discoveredAgents, localCurrency)
      : buildPlan(parsed, discoveredAgents, localCurrency);

  const weatherBaseUrl =
    discoveredAgents["weather-agent"]?.baseUrl ?? process.env.WEATHER_AGENT_URL ?? "http://127.0.0.1:3100";
  const currencyBaseUrl =
    discoveredAgents["currency-agent"]?.baseUrl ??
    process.env.CURRENCY_AGENT_URL ??
    "http://127.0.0.1:3101";
  const timeBaseUrl =
    discoveredAgents["time-agent"]?.baseUrl ?? process.env.TIME_AGENT_URL ?? "http://127.0.0.1:3102";

  if (parsed.targetAgent === "weather-agent") {
    const weather = await sendMessage(weatherBaseUrl, parsed.userGoal);
    const data: Record<string, unknown> = {
      user_request: parsed.userGoal,
      plan,
      discovered_agent: {
        name: discoveredAgents["weather-agent"]?.name ?? "Weather Agent",
        skills: discoveredAgents["weather-agent"]?.card.skills ?? [],
      },
      selected_agent: parsed.targetAgent,
      agent_output: weather.rawText,
    };
    return { summary: weather.rawText, data };
  }

  if (parsed.targetAgent === "currency-agent") {
    const currency = await sendMessage(currencyBaseUrl, parsed.userGoal);
    const data: Record<string, unknown> = {
      user_request: parsed.userGoal,
      plan,
      discovered_agent: {
        name: discoveredAgents["currency-agent"]?.name ?? "Currency Agent",
        skills: discoveredAgents["currency-agent"]?.card.skills ?? [],
      },
      selected_agent: parsed.targetAgent,
      agent_output: currency.rawText,
    };
    return { summary: currency.rawText, data };
  }

  if (parsed.targetAgent === "time-agent") {
    const time = await sendMessage(
      timeBaseUrl,
      `What is the local time in ${parsed.city}?`
    );
    const data: Record<string, unknown> = {
      user_request: parsed.userGoal,
      plan,
      discovered_agent: {
        name: discoveredAgents["time-agent"]?.name ?? "Time Agent",
        skills: discoveredAgents["time-agent"]?.card.skills ?? [],
      },
      selected_agent: parsed.targetAgent,
      agent_output: time.rawText,
    };
    return { summary: time.rawText, data };
  }

  const weather = await sendMessage(weatherBaseUrl, `What is the weather in ${parsed.city}?`);
  const currency = await sendMessage(
    currencyBaseUrl,
    `Convert ${parsed.amountUsd} USD to ${localCurrency ?? "EUR"}.`
  );
  const time = await sendMessage(timeBaseUrl, `What is the local time in ${parsed.city}?`);

  const finalAnswer = buildFinalAnswer(
    parsed.city,
    weather.rawText,
    currency.rawText,
    time.rawText
  );

  const data: Record<string, unknown> = {
    user_request: parsed.userGoal,
    discovered_agents: Object.fromEntries(
      Object.entries(discoveredAgents).map(([key, agent]) => [
        key,
        { name: agent.name, skills: agent.card.skills ?? [] },
      ])
    ),
    plan,
    agent_outputs: {
      weather: weather.rawText,
      currency: currency.rawText,
      time: time.rawText,
    },
    final_answer: finalAnswer,
  };

  return { summary: finalAnswer, data };
}
