import http from "http";

type OllamaGenerateResponse = {
  response?: string;
};

function extractJsonObject(text: string): string {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1 || end < start) {
    throw new Error("Ollama response did not contain a JSON object");
  }

  return text.slice(start, end + 1);
}

async function postJson(url: URL, body: string): Promise<string> {
  const timeoutMs = Number(process.env.OLLAMA_TIMEOUT_MS) || 45000;

  return await new Promise<string>((resolve, reject) => {
    const request = http.request(
      url,
      {
        method: "POST",
        timeout: timeoutMs,
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (response) => {
        let data = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          data += chunk;
        });
        response.on("end", () => {
          const statusCode = response.statusCode ?? 500;
          if (statusCode >= 400) {
            reject(new Error(`Ollama request failed with status ${statusCode}: ${data}`));
            return;
          }

          resolve(data);
        });
      }
    );

    request.on("timeout", () => {
      request.destroy(new Error("Ollama request timed out"));
    });
    request.on("error", reject);
    request.write(body);
    request.end();
  });
}

export async function extractBookingJson(userPrompt: string): Promise<string> {
  const baseUrl = process.env.OLLAMA_BASE_URL ?? "http://127.0.0.1:11434";
  const model = process.env.OLLAMA_MODEL ?? "qwen3:14b";
  const url = new URL("/api/generate", baseUrl);

  const prompt = [
    "Extract hotel booking details from the user request.",
    "Return JSON only.",
    "Do not add markdown fences or any commentary.",
    "Use keys: guest_name, email, credit_card, hotel_name, city, check_in_date, check_out_date, guests, room_type, special_requests.",
    "Use null when a field is missing.",
    "",
    "User request:",
    userPrompt,
  ].join("\n");

  const raw = await postJson(
    url,
    JSON.stringify({
      model,
      prompt,
      stream: false,
      format: "json",
    })
  );

  const parsed = JSON.parse(raw) as OllamaGenerateResponse;
  if (!parsed.response) {
    throw new Error("Ollama response body was missing the generated text");
  }

  return extractJsonObject(parsed.response);
}

export async function selectAgentJson(userPrompt: string): Promise<string> {
  const baseUrl = process.env.OLLAMA_BASE_URL ?? "http://127.0.0.1:11434";
  const model = process.env.OLLAMA_MODEL ?? "qwen3:14b";
  const url = new URL("/api/generate", baseUrl);

  const raw = await postJson(
    url,
    JSON.stringify({
      model,
      prompt: userPrompt,
      stream: false,
      format: "json",
    })
  );

  const parsed = JSON.parse(raw) as OllamaGenerateResponse;
  if (!parsed.response) {
    throw new Error("Ollama response body was missing the generated text");
  }

  return extractJsonObject(parsed.response);
}
