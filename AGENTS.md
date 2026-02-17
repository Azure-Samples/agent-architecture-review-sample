# Agents Guide — Architecture Review Agent Sample

> This file helps AI coding agents (GitHub Copilot, Copilot Workspace, Codespaces agents, etc.) understand and work effectively with this repository.

---

## Repository Purpose

This is an **AI-powered Architecture Review Agent** that analyses software architecture descriptions and generates interactive diagrams. It accepts any input format (YAML, Markdown, plaintext, code, design docs, prose) and returns structured risk assessments, Excalidraw diagrams, PNG exports, and actionable recommendations.

---

## Project Structure

```
agent-architecture-review-sample/
├── main.py              # Hosted agent entry point (Microsoft Agent Framework / Foundry)
├── api.py               # FastAPI backend (REST API for the web UI)
├── tools.py             # Core engine — all tool logic (parser, risk detector, diagram renderer, MCP client, PNG export)
├── run_local.py         # CLI runner for local testing (no Azure required for structured inputs)
├── agent.yaml           # Foundry hosted agent deployment manifest
├── requirements.txt     # Python dependencies (pinned versions)
├── pyproject.toml       # Pytest configuration
├── Dockerfile           # Container for hosted agent deployment
├── Dockerfile.web       # Container for web app deployment (FastAPI + React)
├── deployment.md        # Step-by-step deployment & RBAC guide
├── frontend/            # React UI (Vite + Excalidraw)
│   ├── src/App.jsx      # Main React app with input, tabs, results
│   ├── src/api.js       # API client — calls FastAPI backend
│   └── src/components/  # Summary, RiskTable, ComponentMap, DiagramViewer, Recommendations
├── scenarios/           # Pre-built demo architecture files (YAML, Markdown)
├── tests/               # Pytest test suite
│   ├── conftest.py      # Shared fixtures (sample components, connections)
│   ├── test_tools.py    # Unit tests for tools.py functions
│   ├── test_api.py      # FastAPI endpoint tests
│   └── test_integration.py  # Integration tests
├── scripts/             # Automation scripts
│   ├── windows/         # PowerShell: setup.ps1, dev.ps1, deploy-webapp.ps1, teardown.ps1
│   └── linux-mac/       # Bash: setup.sh, dev.sh, deploy-webapp.sh, teardown.sh
└── output/              # Generated outputs (auto-created): .excalidraw, .png, .json
```

---

## Key Files and Responsibilities

| File | Role | When to modify |
|------|------|----------------|
| `tools.py` | **Core engine** — parser, LLM inference, risk detection, Excalidraw/PNG rendering, component mapping, report builder | Adding analysis capabilities, new parsers, new risk detectors, diagram improvements |
| `main.py` | Hosted agent entry point — registers tools with Microsoft Agent Framework, defines agent instructions | Changing agent behaviour, adding/removing tools, modifying system prompt |
| `api.py` | FastAPI REST API — exposes review pipeline as HTTP endpoints, serves React frontend in production | Adding/modifying API endpoints, changing request validation, CORS config |
| `run_local.py` | CLI test runner — runs the full pipeline locally with Rich console output | Improving CLI experience, adding CLI flags |
| `agent.yaml` | Foundry deployment manifest — defines agent name, model, protocols, environment variables | Changing deployment config, model, environment variables |
| `requirements.txt` | Python dependencies — pinned versions | Adding/updating dependencies |

---

## Architecture and Data Flow

```
Input (any format) → smart_parse() → [rule-based OR LLM fallback]
    → analyze_risks() → generate_excalidraw_elements() → export_png()
    → build_component_map() → build_review_report()
```

### Core Pipeline (`tools.py`)

1. **`smart_parse(content)`** — Tries rule-based parsing first (YAML → `_parse_yaml`, Markdown → `_parse_markdown`, text → `_parse_text`). If it extracts ≤1 component, automatically falls back to `infer_architecture_llm()`.
2. **`analyze_risks(components, connections)`** — Template-based risk detection across 4 categories: SPOF, scalability, security, anti-patterns. LLM-inferred inputs carry their own risks.
3. **`generate_excalidraw_elements()`** — Builds Excalidraw JSON with layered layout (frontend → gateway → service → database).
4. **`export_png()`** — Renders PNG using Pillow with the same layout engine.
5. **`build_component_map()`** — Dependency analysis with fan-in/fan-out metrics.
6. **`build_review_report()`** — Composes executive summary, risk assessment, component map, diagram info, and prioritised recommendations.

### Two Deployment Paths

- **Option A — Web App**: `api.py` (FastAPI) + `frontend/` (React). Deployed to Azure App Service via `Dockerfile.web`.
- **Option B — Hosted Agent**: `main.py` (Agent Framework). Deployed to Microsoft Foundry via `Dockerfile` and VS Code Foundry extension (v2 hosted agent services).

Both share the same core engine in `tools.py`.

---

## Technology Stack

- **Python 3.11+**
- **Microsoft Agent Framework** (`azure-ai-agentserver-agentframework` v1.0.0b12) — hosted agent runtime (v2 hosted agent services)
- **Azure OpenAI** (GPT-4.1) — LLM backend via `AzureOpenAIChatClient`
- **FastAPI** + **Uvicorn** — REST API
- **React** + **Vite** — frontend UI
- **Excalidraw MCP Server** — interactive diagram rendering via Model Context Protocol
- **Pillow** — PNG diagram export
- **PyYAML** — YAML parsing
- **Rich** — CLI output formatting
- **Pytest** — test framework (async via `asyncio_mode = "auto"`)

---

## Environment Setup

### Prerequisites
- Python 3.11+
- Node.js (for frontend development)
- (Optional) Azure OpenAI access for LLM inference

### Quick Setup

```powershell
# Windows
.\scripts\windows\setup.ps1
```

```bash
# Linux / macOS
bash scripts/linux-mac/setup.sh
```

### Manual Setup

```bash
python -m venv .venv
# Activate: .\.venv\Scripts\Activate.ps1 (Windows) or source .venv/bin/activate (Unix)
pip install -r requirements.txt
cp .env.template .env  # then edit with your Azure OpenAI settings
```

### Required Environment Variables

```dotenv
# Set ONE of these endpoints:
PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Model
MODEL_DEPLOYMENT_NAME=gpt-4.1

# Authentication (API key or DefaultAzureCredential via az login)
AZURE_OPENAI_API_KEY=your-key-here
```

---

## Running and Testing

### Run Locally (CLI)

```bash
python run_local.py scenarios/ecommerce.yaml              # Rule-based parse
python run_local.py scenarios/event_driven.md              # Markdown parse
python run_local.py --text "LB -> API -> DB"               # Inline text
python run_local.py README.md --infer                      # Force LLM inference
python run_local.py scenarios/ecommerce.yaml --render      # With MCP diagram
```

### Run Web App (dev mode)

```powershell
.\scripts\windows\dev.ps1    # Starts FastAPI (port 8000) + Vite (port 5173)
```

Or manually:
```bash
# Terminal 1: python -m uvicorn api:app --reload --port 8000
# Terminal 2: cd frontend && npm install && npx vite --port 5173
```

### Run Hosted Agent (local)

```bash
python main.py   # Starts on http://localhost:8088
```

### Run Tests

```bash
pytest                      # All tests
pytest tests/test_tools.py  # Unit tests for core engine
pytest tests/test_api.py    # API endpoint tests
pytest -v --tb=short        # Verbose output (configured in pyproject.toml)
```

---

## API Endpoints (FastAPI — `api.py`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/review` | Submit architecture text for full review (`{"content": "...", "force_infer": false}`) |
| `POST` | `/api/review/upload` | Upload a file for review (multipart form) |
| `POST` | `/api/infer` | LLM inference only (`{"content": "..."}`) |
| `GET` | `/api/download/png/{run_id}` | Download PNG diagram |
| `GET` | `/api/download/excalidraw/{run_id}` | Download Excalidraw JSON |
| `GET` | `/api/health` | Health check |

---

## Agent Tools (Hosted Agent — `main.py`)

| Tool | Description |
|------|-------------|
| `review_architecture(content, render_diagram)` | Full pipeline — parse → risks → diagram → PNG → component map → report |
| `infer_architecture(content)` | LLM inference only — extract components/connections from unstructured text |

---

## Coding Conventions

- **All core logic lives in `tools.py`** — both `main.py` and `api.py` import from it. Never duplicate logic.
- **Async functions** — `smart_parse()`, `infer_architecture_llm()`, and MCP rendering are async. Use `await` when calling them.
- **Standard data schema** — All parsers return `{"components": [...], "connections": [...], "metadata": {...}, "detected_format": str, "parsing_sufficient": bool}`.
- **Component schema** — `{"id": str, "name": str, "type": str, "description": str, "replicas": int, "technology": str}`.
- **Connection schema** — `{"source": str, "target": str, "label": str, "type": str}`.
- **Risk schema** — `{"component": str, "severity": "critical"|"high"|"medium"|"low", "issue": str, "recommendation": str}`.
- **Type inference** — Component types are inferred from names via `_TYPE_KEYWORDS` in `tools.py`. Valid types: `database`, `cache`, `queue`, `gateway`, `frontend`, `storage`, `external`, `monitoring`, `service` (default).
- **Input size limit** — API enforces 500,000 character max (`MAX_INPUT_SIZE` in `api.py`).
- **run_id validation** — Download endpoints validate `run_id` as hex string to prevent path traversal.
- **Logging** — Uses `logging.getLogger("arch-review")`. CLI runner suppresses it; API lets it propagate.
- **Error handling** — API returns proper HTTP status codes (400, 413, 422, 500). LLM failures fall back gracefully to rule-based results.

---

## Testing Conventions

- Tests live in `tests/` and follow `test_*.py` naming.
- Shared fixtures are in `tests/conftest.py` — provides `sample_components`, `sample_connections`, and specialised fixtures for risk detection scenarios.
- Sample data for tests is in `tests/sample_data.py`.
- Pytest config is in `pyproject.toml` — uses `asyncio_mode = "auto"` for async tests.
- No Azure/LLM dependencies required for unit tests — they test the rule-based engine.

---

## Common Tasks for Agents

### Adding a new risk detector
1. Add a `_detect_<category>()` function in `tools.py` (Section 2 — Risk Detector).
2. Call it from `analyze_risks()`.
3. Add tests in `tests/test_tools.py`.

### Adding a new input parser
1. Add a `_parse_<format>()` function in `tools.py` (Section 1 — Architecture Parser).
2. Update `_detect_format()` to recognise the new format.
3. Wire it into `parse_architecture()`.
4. Add tests with sample inputs.

### Adding a new API endpoint
1. Add the endpoint in `api.py` with proper Pydantic models, input validation, and error handling.
2. Add tests in `tests/test_api.py`.

### Adding a new agent tool
1. Define the async function in `main.py` with `Annotated` type hints for parameters.
2. Add it to the `tools=[...]` list in `main()`.
3. Update `INSTRUCTIONS` to describe the new tool's purpose.

### Modifying the frontend
1. React components are in `frontend/src/components/`.
2. API calls go through `frontend/src/api.js`.
3. Vite dev server proxies `/api` to `localhost:8000` (configured in `frontend/vite.config.js`).

### Adding a demo scenario
1. Create a YAML or Markdown file in `scenarios/`.
2. Follow the schema used by existing scenarios (components/connections for YAML, ## Components/## Connections headers for Markdown).
3. Update `scenarios/README.md`.

---

## Deployment

- **Web App → Azure App Service**: `.\scripts\windows\deploy-webapp.ps1 -ResourceGroup <rg> -AppName <name>`
- **Hosted Agent → Microsoft Foundry**: VS Code Foundry extension → `Microsoft Foundry: Deploy Hosted Agent`
- **Teardown**: `.\scripts\windows\teardown.ps1 -ResourceGroup <rg>`
- Full deployment guide: `deployment.md`
