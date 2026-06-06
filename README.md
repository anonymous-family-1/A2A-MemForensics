# A2A-MemForensics

A memory-forensics research artifact for the Agent-to-Agent (A2A) protocol.
The repository contains two controlled multi-agent environments that produce A2A protocol artifacts in volatile memory, and a reconstruction tool that recovers those artifacts from a raw memory image.

## Repository Layout

```
A2A-MemForensics/
├── A2A-Test-Beds/              # Multi-agent travel-assistant system
├── hotel-booking-agent-card-poc/  # Hotel-booking PoC with poisoning simulation
└── tool/                       # Forensics reconstruction tool
    ├── a2a_reconstruct.py      # CLI tool
    ├── test.vmem       # Bundled sample memory image
    └── ui/
        ├── app_ui.py           # PyQt6 GUI
        └── requirements.txt
```

---

## Requirements

### For the agent test beds

- **Node.js 18 or later** — <https://nodejs.org>
- **npm** (bundled with Node.js)
- Outbound internet access for live API calls (Open-Meteo, Frankfurter)
- **Optional**: a running [Ollama](https://ollama.com) instance for LLM-assisted planning and booking extraction

### For the forensics tool

- **Python 3.10 or later**
- **strings(1)** from GNU binutils (`apt install binutils` / `brew install binutils`)
- For the GUI only: `PyQt6 >= 6.4.0`

---

## Part 1 — A2A-Test-Beds

A four-agent travel-assistant system.

| Agent | Port | Skills |
|---|---|---|
| weather-agent | 3100 | `get_current_weather`, `get_weather_forecast` |
| currency-agent | 3101 | `convert_currency` |
| time-agent | 3102 | `get_local_time` |
| planner-agent | 3103 | `prepare_trip` |

### Install

Run once from the repository root:

```bash
cd A2A-Test-Beds/weather-agent  && npm install
cd ../currency-agent            && npm install
cd ../time-agent                && npm install
cd ../planner-agent             && npm install
cd ../..
```

### Run

From `A2A-Test-Beds/`:

```bash
# Single agent
node run_pipeline.js --agent weather-agent  "What is the current weather in Tokyo?"
node run_pipeline.js --agent weather-agent  "Tell me the weather in Paris for the next 5 days."
node run_pipeline.js --agent currency-agent "Convert 100 USD to JPY."
node run_pipeline.js --agent currency-agent "How much is 250 USD in GBP?"
node run_pipeline.js --agent time-agent     "What is the local time in Tokyo?"
node run_pipeline.js --agent time-agent     "What time is it in Paris?"

# Full multi-agent pipeline
node run_pipeline.js --agent all "I am traveling to Paris with 100 USD. Help me prepare."

# Ollama-assisted planning (requires a running Ollama instance)
OLLAMA_BASE_URL=http://127.0.0.1:11434 OLLAMA_MODEL=qwen3:14b \
  node run_pipeline.js --agent all --mode ollama \
  "I am traveling to Paris with 100 USD. Help me prepare."
```

The runner starts only the agents required for the selected target.
`--agent all` starts all four agents.



### Ollama proxy (optional)

`ollama_proxy.js` forwards requests from a network address to a local Ollama instance.

```bash
OLLAMA_PROXY_HOST=0.0.0.0 \
OLLAMA_PROXY_PORT=11434 \
OLLAMA_TARGET_BASE=http://127.0.0.1:11434 \
  node ollama_proxy.js
```

---

## Part 2 — Hotel-Booking Agent-Card Poisoning PoC

A three-agent booking system that includes a safe simulation of agent-card poisoning.

| Agent | Port | Skill |
|---|---|---|
| hotel-booking-agent | 3201 | `book_hotel` |
| decoy-booking-agent (Premium) | 3202 | `book_hotel_priority` |
| client-agent | 3200 | `book_hotel_via_orchestration` |

### Install

```bash
cd hotel-booking-agent && npm install
cd ../decoy-booking-agent && npm install
cd ../client-agent && npm install
cd ../..
```

### Run — normal booking flow

```bash
cd hotel-booking-agent-card-poc
node run_pipeline.js "Book the Grand Palace Hotel in Paris for John Smith. \
  My email is john@example.com, my credit card is 4111111111111111, \
  check-in is 2025-07-10, check-out is 2025-07-13, 2 guests, deluxe room."
```

### Run — agent-card poisoning simulation

```bash
SIMULATE_AGENT_CARD_POISONING=1 node run_pipeline.js \
  "Book the Grand Palace Hotel in Paris for John Smith. \
  My email is john@example.com, my credit card is 4111111111111111, \
  check-in is 2025-07-10, check-out is 2025-07-13, 2 guests, deluxe room."
```

In poisoning mode the client sends both agent cards to Ollama for selection.
If Ollama is unreachable the client falls back to heuristic card scoring.
The decoy agent only receives a redacted payload — email and credit card are masked.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen3:14b` | Model name |
| `HOTEL_AGENT_URL` | `http://127.0.0.1:3201` | Real booking agent |
| `DECOY_HOTEL_AGENT_URL` | `http://127.0.0.1:3202` | Decoy agent |
| `SIMULATE_AGENT_CARD_POISONING` | `0` | Set to `1` to enable poisoning sim |
| `OLLAMA_TIMEOUT_MS` | `45000` | Request timeout (ms) |

---

## Part 3 — Forensics Reconstruction Tool

### Install Python dependencies

```bash
pip install PyQt6>=6.4.0   # GUI only; not needed for CLI
```

### CLI — reconstruct from a memory image

```bash
cd tool
python3 a2a_reconstruct.py test.vmem
```

The tool runs `strings` on the image, carves JSON objects, classifies them as A2A types, and reconstructs the interaction chain.

**Output flags:**

| Flag | Description |
|---|---|
| `--output report.json` | Write structured JSON report |
| `--text-output report.txt` | Write full text reconstruction to file |
| `--dump objects.json` | Write flat JSON array of all carved objects with memory offsets |
| `--strings-bin /path/to/strings` | Override the `strings(1)` binary path |
| `--min-len N` | Minimum string length passed to `strings` (default: 6) |

**Examples:**

```bash
# Basic reconstruction printed to stdout
python3 a2a_reconstruct.py test.vmem

# Save structured JSON report
python3 a2a_reconstruct.py test.vmem --output report.json

# Save both text and JSON
python3 a2a_reconstruct.py test.vmem \
  --output report.json --text-output report.txt

# Dump all carved A2A objects with memory offsets
python3 a2a_reconstruct.py test.vmem --dump objects.json
```

### GUI

```bash
cd tool/ui
pip install -r requirements.txt
python3 app_ui.py
```

Drop a `.vmem` file onto the interface or use **Browse** to select one, then click **Analyze**.

The GUI has four tabs:

- **Summary** — counts and agent card overview
- **Interactions** — step-by-step reconstruction per interaction
- **Raw Objects** — every carved JSON object with its memory offset, filterable by type
- **Memory Map** — visual layout of object positions within the image


### Sample output — GUI

**Interactions tab** — the tool reconstructs the interaction chain containing agent discovery, task submission, task completion, recovered from memory.

![Interactions tab — reconstructed interaction chain](img/interaction.png)

**Raw Objects tab — Agent Card** — the carved agent card JSON is shown with its exact memory offset. The inspector on the right expands every field.

![Raw Objects tab — Agent Card detail](img/agent-card.png)

**Raw Objects tab — RPC Request** — the carved `message/send` JSON-RPC request, including the structured booking payload embedded in the message text.

![Raw Objects tab — RPC Request detail](img/request.png)

**Raw Objects tab — RPC Response** — the carved task response object containing the final booking confirmation text and task identifiers.

![Raw Objects tab — RPC Response detail](img/response.png)

---

