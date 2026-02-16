# Building an AI Architecture Reviewer with Microsoft Agent Framework & Hosted Agents

*Turn natural-language architecture descriptions into risk reports and interactive diagrams — deployed as a hosted agent on Microsoft Foundry in minutes.*

---

## The Problem Every Engineering Team Faces

You've been there. Someone pastes an architecture sketch into a Slack thread — a tangle of arrows, service names, and hopeful annotations. A staff engineer squints at it, flags two single-points-of-failure, and moves on. Three months later, one of those SPOFs takes down production at 2 AM.

Architecture review is **critical** but chronically **under-resourced**. Humans are great at deep analysis, but inconsistent at catching boilerplate risks across dozens of designs. What if you could give every pull request, design doc, or whiteboard photo the same rigorous review — automatically?

That's exactly what the **Architecture Review Agent** sample does. And building it taught us how powerful the [Microsoft Agent Framework](https://github.com/microsoft/agents) and Microsoft Foundry's **Hosted Agents** can be for shipping production AI tools fast.

---

## What We Built

The Architecture Review Agent is an AI-powered architecture reviewer that:

1. **Accepts any input** — YAML, Markdown, plaintext arrows, READMEs, Terraform configs, even meeting notes
2. **Parses or infers** the architecture using rule-based parsers with automatic LLM fallback
3. **Detects risks** — SPOFs, scalability bottlenecks, security gaps, anti-patterns
4. **Generates interactive diagrams** — via Excalidraw with PNG export
5. **Produces structured reports** — executive summary, severity-ranked risks, component dependency maps, prioritised recommendations

Feed it this:

```text
Our platform uses React for the frontend, served through CloudFront CDN.
All API calls go through a Kong API Gateway which routes to three
microservices: User Service, Order Service, and Inventory Service.
Each service has its own PostgreSQL database.
```

And it returns a complete architecture review with 10 identified components, risk analysis, an interactive diagram, and actionable recommendations — in seconds.

### Four Ways to Run It — Two Ways to Deploy

| Mode | What It Is | Infrastructure |
|------|-----------|----------------|
| **CLI** | Local pipeline runner — no Azure required for structured inputs | Your machine |
| **Web UI** | React + FastAPI — interactive browser-based review | Your machine (dev) or **Azure App Service** (prod) |
| **Hosted Agent** | OpenAI Responses-compatible API via Agent Framework | Your machine (dev) or **Microsoft Foundry Agent Service** (prod) |

For production deployment, the Architecture Review Agent offers **two distinct options** — each with different trade-offs. We'll dive into both later in this post.

---

## Why Microsoft Agent Framework?

When we started the Architecture Review Agent, we had working Python functions for parsing, risk detection, and diagram generation. The question was: how do we turn these into an agent that can reason about architecture, choose the right tools, and produce coherent reports?

### The Framework Handles the Hard Parts

The [Microsoft Agent Framework](https://github.com/microsoft/agents) (`azure-ai-agentserver-agentframework`) gives you:

- **Tool registration** — expose Python functions as agent tools with type annotations
- **Conversation management** — the framework handles message routing, context windows, and tool-call orchestration
- **Protocol compliance** — your agent speaks the OpenAI Responses API out of the box
- **Deployment-ready** — one `agent.yaml` manifest and you're deployable to Microsoft Foundry

Here's what our entire agent entry point looks like:

```python
from agent_framework.azure import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework

async def main():
    async with (
        DefaultAzureCredential() as credential,
        AzureAIAgentClient(
            project_endpoint=PROJECT_ENDPOINT,
            model_deployment_name=MODEL_DEPLOYMENT_NAME,
            credential=credential,
        ) as client,
    ):
        agent = client.create_agent(
            name="Architecture Review Agent",
            instructions=INSTRUCTIONS,
            tools=[review_architecture, infer_architecture],
        )
        server = from_agent_framework(agent)
        await server.run_async()
```

That's it. Two tool functions, a set of instructions, and the framework handles everything else — HTTP server, request parsing, tool execution, response formatting.

### Tools Are Just Python Functions

No complex DSLs or config files. Your tools are async Python functions with type annotations:

```python
async def review_architecture(
    content: Annotated[str, "Architecture description — ANY format"],
    render_diagram: Annotated[bool, "Render interactive diagram via MCP"] = True,
) -> str:
    """Run a complete architecture review."""
    parsed = await smart_parse(content)
    risks = analyze_risks(parsed["components"], parsed["connections"])
    diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
    report = build_review_report(parsed, risks, comp_map, diagram_info)
    return json.dumps(report, indent=2)
```

The type annotations become the tool's schema. The docstring becomes the tool's description. The framework's model uses both to decide when and how to call your tool.

---

## Two Deployment Options: Web App vs Hosted Agent

Here's where things get interesting. The Architecture Review Agent ships with **two production deployment paths**, each built on the same `tools.py` core. Choose the one that fits your team's operational model — or run both side-by-side.

### Option A — Web App (Azure App Service)

This is the traditional full-stack approach: a **FastAPI** backend wraps the same tool functions, and a **React** frontend provides an interactive browser experience with Excalidraw diagrams, drag-and-drop file upload, and downloadable outputs.

```
React UI ──▶ FastAPI (api.py) ──▶ tools.py ──▶ Azure OpenAI
```

You deploy it as a Docker container to **Azure App Service** — you own the API surface, the scaling rules, and the authentication layer. The REST API exposes custom endpoints (`/api/review`, `/api/infer`, `/api/download/*`) that you can integrate into existing tooling, CI/CD pipelines, or internal dashboards.

**When to choose this:**
- You want a **custom browser UI** for your engineering team
- You need to integrate the review API into existing tools (Slack bots, CI checks, internal portals)
- You prefer **full control** over infrastructure, scaling, and auth
- You already have App Service infrastructure and operational patterns

Deploy with one command:
```powershell
.\scripts\windows\deploy.ps1 -target webapp -ResourceGroup arch-review-rg -AppName arch-review-web
```

### Option B — Hosted Agent (Microsoft Foundry Agent Service)

This is the cloud-native agent approach. Microsoft Foundry's **Hosted Agents** let you deploy your agent as a managed, scalable API without managing infrastructure.

```
Clients ──▶ Microsoft Foundry (managed) ──▶ main.py (Agent Framework) ──▶ tools.py ──▶ Azure OpenAI
```

A hosted agent is a container that runs on **Foundry-managed compute**. You define your agent in an `agent.yaml` manifest:

```yaml
name: Architecture Review Agent
template:
  kind: hosted
  protocols:
    - protocol: responses
  cpu: "1"
  memory: "2Gi"
resources:
  - kind: model
    id: gpt-4.1
    name: chat
```

Then deploy with a single command:

```bash
azd ai agent deploy
```

Azure handles everything:
- **Container build & hosting** — via Azure Container Registry Tasks, deployed to Foundry-managed infrastructure
- **Managed identity** — system-assigned identity with RBAC, no API keys in your container
- **Auto-scaling** — 0 → 5 replicas with scale-to-zero support (you don't pay when idle)
- **Conversation persistence** — the Agent Service stores and manages conversation state across requests
- **API compliance** — your agent automatically exposes the OpenAI Responses API
- **Observability** — built-in OpenTelemetry tracing with Azure Monitor integration
- **Channel publishing** — publish your agent to **Microsoft Teams**, **Microsoft 365 Copilot**, a **Web App preview**, or a **stable API endpoint** without writing additional code

**When to choose this:**
- You want a **managed, scalable API** without infrastructure overhead
- You need the agent accessible via **Teams or M365 Copilot** channels
- You want **conversation persistence** managed by the platform
- You prefer **scale-to-zero** economics (don't pay for idle compute)
- You want built-in **observability** without configuring monitoring infrastructure

Deploy with one command:
```powershell
.\scripts\windows\deploy.ps1 -target agent -ResourceGroup arch-review-rg -ProjectName arch-review
```

### Side-by-Side Comparison

| | **Web App (App Service)** | **Hosted Agent (Microsoft Foundry)** |
|---|---|---|
| **API style** | Custom REST endpoints | OpenAI Responses API (automatic) |
| **UI included** | Yes — React + Excalidraw | No (API only; use Foundry Playground or channels) |
| **Scaling** | App Service Plan (manual / auto-scale rules) | Platform-managed (0–5 replicas, scale-to-zero) |
| **Identity & auth** | Configured by you | System-assigned managed identity (automatic) |
| **Conversations** | Stateless REST (you manage state) | Platform-managed persistence |
| **Channel publishing** | N/A | Teams, M365 Copilot, Web preview |
| **Observability** | Bring your own (App Insights, etc.) | Built-in OpenTelemetry + Azure Monitor |
| **Operational overhead** | Medium — you manage the App Service | Low — the platform manages compute |
| **Infrastructure cost model** | Always-on App Service Plan | Scale-to-zero (pay per use) |

> **Pro tip:** You can run both simultaneously. Use the Web App for your team's browser-based reviews and the Hosted Agent for API consumers, Teams integration, and M365 Copilot access.

### The Deployment Experience

We built automated deployment scripts that handle the full lifecycle for both options:

```powershell
# Option A: Deploy the web app to Azure App Service
.\scripts\windows\deploy.ps1 -target webapp -ResourceGroup arch-review-rg -AppName arch-review-web

# Option B: Deploy the hosted agent to Microsoft Foundry
.\scripts\windows\deploy.ps1 -target agent -ResourceGroup arch-review-rg -ProjectName arch-review

# Clean up either option
.\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg
```

From zero to a production endpoint in under 10 minutes — for either path.

---

## Anatomy of the Architecture Review Pipeline

Let's walk through what happens when someone submits an architecture for review:

### Step 1: Smart Parsing

The Architecture Review Agent doesn't force a specific input format. The `smart_parse` function detects the format and routes accordingly:

```
YAML with components/connections → Rule-based YAML parser
Markdown with ## headers        → Markdown parser
Plaintext with arrows (→, ->)   → Arrow parser
Everything else                 → LLM inference (automatic fallback)
```

The LLM fallback is key. When someone pastes a README or design doc, the rule-based parsers yield ≤1 component. The Architecture Review Agent automatically calls Azure OpenAI to infer the architecture:

```python
async def smart_parse(content: str) -> dict:
    parsed = parse_architecture(content)
    if len(parsed.get("components", [])) <= 1:
        # Auto-fallback to LLM inference
        return await infer_architecture_llm(content)
    return parsed
```

This means the agent genuinely accepts **any** input — from a formal YAML spec to informal meeting notes.

### Step 2: Risk Detection

Two engines run depending on the parsing path:

**Template-based** (for structured inputs) — fast pattern matching:
- **SPOF detection**: Components with 1 replica and ≥2 dependants
- **Scalability**: Shared resources used by ≥3 services
- **Security**: Frontend-to-database direct access, missing gateways
- **Anti-patterns**: Multiple services writing to the same datastore

**LLM-generated** (for inferred inputs) — the model produces context-aware risks that go beyond templates, catching architecture-specific issues like PCI compliance gaps or observability blind spots.

### Step 3: Diagram Generation

The Architecture Review Agent generates Excalidraw diagram elements programmatically — calculating positions, creating colour-coded nodes by component type, and drawing labelled connection arrows:

| Type | Colour | Keywords |
|------|--------|----------|
| Database | Yellow | postgres, mysql, mongodb... |
| Cache | Orange | redis, memcached, cdn |
| Queue | Purple | kafka, rabbitmq, sqs... |
| Gateway | Violet | load balancer, nginx, envoy... |
| Frontend | Blue | react, angular, vue... |
| External | Red | stripe, twilio... |

The output is a standard `.excalidraw` file you can open at [excalidraw.com](https://excalidraw.com) or embed in the React web UI.

### Step 4: Structured Report

Everything rolls into a JSON report with:
- **Executive summary** — component count, connection count, risk level, format detected
- **Risks** — grouped by severity (critical → high → medium → low)
- **Component map** — dependency analysis with fan-in/fan-out metrics
- **Recommendations** — prioritised actions derived from identified risks

---

## The Web UI: React + Excalidraw + FastAPI

For teams that want a visual experience, the Architecture Review Agent includes a full web interface:

- **Drag-and-drop file upload** — or paste architecture text directly
- **Interactive Excalidraw diagrams** — zoom, pan, and edit the generated architecture
- **Tabbed results** — switch between Diagram, Risks, Components, and Recommendations
- **Download outputs** — PNG and `.excalidraw` files for offline use

The backend is a lightweight FastAPI service wrapping the same tool functions used by the hosted agent. The frontend is React + Vite with the `@excalidraw/excalidraw` component for interactive diagram viewing.

### Architecture of the Architecture Review Agent Itself

All three interfaces — CLI, Web App, and Hosted Agent — share the same `tools.py` core. Write once, deploy three ways.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Shared Core: tools.py                        │
│  smart_parse · analyze_risks · generate_diagram · export_png · ...   │
└────────────┬────────────────────┬────────────────────┬───────────────┘
             │                    │                    │
   ┌─────────▼───────────┐  ┌─────▼───────────┐  ┌─────▼────────────┐
   │  CLI                │  │  Option A       │  │  Option B        │
   │  run_local.py       │  │  Web App        │  │  Hosted Agent    │
   │                     │  │                 │  │                  │
   │  Your machine       │  │  React UI       │  │  main.py         │
   │  No Azure needed    │  │  + FastAPI      │  │  Agent Framework │
   │  (structured input) │  │  (api.py)       │  │                  │
   └─────────────────────┘  │                 │  │  OpenAI          │
                            │  Custom REST    │  │  Responses API   │
                            │  /api/review    │  │  /responses      │
                            │  /api/infer     │  │                  │
                            │                 │  │  Managed by      │
                            │  Deploy to:     │  │  Microsoft       │
                            │  App Service    │  │  Foundry         │
                            │  + ACR          │  │                  │
                            │                 │  │  Auto-scaling    │
                            │  You manage:    │  │  Managed identity│
                            │  Scaling, auth, │  │  Conversations   │
                            │  infra          │  │  Teams / Copilot │
                            └─────────────────┘  └──────────────────┘
```

---

## Getting Started in 5 Minutes

### Step 1: Local CLI (No Azure Required)

```bash
git clone <repo-url>
cd agent-architecture-review-sample
.\scripts\windows\setup.ps1  # or bash scripts/linux-mac/setup.sh on Linux/macOS

python run_local.py examples/ecommerce.yaml
```

This runs the full pipeline locally using rule-based parsing — no API keys needed.

### Step 2: Web UI (Local Development)

```powershell
.\scripts\windows\dev.ps1
# Opens at http://localhost:5173
```

### Step 3: Choose Your Deployment Path

#### Option A — Deploy the Web App to Azure App Service

Best if you want a **custom UI** and full control over your API surface.

```powershell
.\scripts\windows\deploy.ps1 -target webapp -ResourceGroup arch-review-rg -AppName arch-review-web
```

Builds the Docker image via ACR Tasks, provisions App Service, and configures everything from your `.env` file. Your team gets a browser-based architecture review tool with interactive Excalidraw diagrams.

#### Option B — Deploy as a Hosted Agent on Microsoft Foundry

Best if you want a **managed, scalable API** with zero infrastructure overhead and channel publishing.

```powershell
.\scripts\windows\deploy.ps1 -target agent -ResourceGroup arch-review-rg -ProjectName arch-review
```

Provisions Azure AI Services, deploys a model, and deploys your agent to Foundry-managed infrastructure. Once deployed, you can publish the agent to **Microsoft Teams**, **M365 Copilot**, or a **stable API endpoint** — all from the Foundry portal.

#### Run Both

There's no reason you can't run both simultaneously — use the Web App for browser-based reviews by your architecture team, and the Hosted Agent for API consumers, Teams bots, and M365 Copilot integration.

---

## Lessons Learned

### 1. Start with Pure Functions, Add the Agent Later

We wrote `tools.py` (parsers, risk detector, diagram generator) as plain Python functions first. The agent layer (`main.py`) is thin — it just wires tools to the framework. This made testing trivial and kept the agent code minimal.

### 2. Smart Fallback > Strict Validation

Rather than rejecting inputs that don't match a schema, we fall back to LLM inference. This single design decision — `if len(components) <= 1: use_llm()` — made the Architecture Review Agent genuinely useful for unstructured inputs like design docs and READMEs.

### 3. Same Tools, Multiple Surfaces

The agent, the API, and the CLI all call the same functions. When we improved risk detection, all three surfaces got the improvement immediately. When we added PNG export, it was available everywhere.

### 4. Offer Two Deployment Paths — Let Teams Choose

Not every team wants managed infrastructure, and not every team wants to manage their own. By packaging the Architecture Review Agent as both a traditional web app (App Service) and a hosted agent (Foundry), we let teams pick the model that fits their operations. The key enabler: both paths call the same `tools.py` functions. The deployment layer is just plumbing.

### 5. Hosted Agents Remove Operational Burden

For the hosted agent path, we didn't have to think about container orchestration, auto-scaling, API gateway configuration, or conversation state management. The `agent.yaml` manifest plus `azd ai agent deploy` handled it. Scale-to-zero means dev/test agents cost nothing when idle. And channel publishing (Teams, M365 Copilot) came for free. For a small team, this is transformative.

### 6. The Web App Gives You Control

For the web app path, we got a custom REST API surface, an interactive React UI with Excalidraw, and the ability to integrate the review API into CI/CD pipelines, Slack bots, or internal dashboards. This matters when your users want a visual, self-serve experience rather than an API-first workflow.

### 7. Excalidraw MCP Is a Game-Changer for Diagrams

The [Excalidraw MCP server](https://github.com/excalidraw/excalidraw-mcp) lets agents generate interactive, editable diagrams — not static images. Users can open the output, drag components around, add annotations, and export in any format. This makes AI-generated output feel like a starting point, not a final product.

---

## What's Next

- **GitHub Action** — run the Architecture Review Agent on every PR that touches architecture docs
- **Multi-architecture comparison** — diff two versions of an architecture and highlight changes
- **Cost estimation** — integrate Azure pricing APIs to estimate infrastructure costs from the architecture
- **Compliance frameworks** — built-in checks for SOC 2, HIPAA, PCI DSS, GDPR

---

## Try It Yourself

The Architecture Review Agent sample is open source and ready to run:

1. **Clone the repo** — `git clone <repo-url>`
2. **Run setup** — `.\scripts\windows\setup.ps1`
3. **Review an architecture** — `python run_local.py examples/ecommerce.yaml`
4. **Deploy your way:**
   - **Option A (Web App):** `.\scripts\windows\deploy.ps1 -target webapp -ResourceGroup my-rg -AppName arch-review-web`
   - **Option B (Hosted Agent):** `.\scripts\windows\deploy.ps1 -target agent -ResourceGroup my-rg -ProjectName arch-review`

The Microsoft Agent Framework makes building production AI agents surprisingly straightforward. If you have domain expertise wrapped in Python functions, you're closer to a deployed agent than you think — and you get to choose whether you want managed cloud infrastructure or full control.

---

## Resources

- [Microsoft Agent Framework](https://github.com/microsoft/agents) — the framework powering the Architecture Review Agent
- [Microsoft Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/hosted-agents) — managed agent deployment
- [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/) — infrastructure-as-code deployment
- [Excalidraw MCP Server](https://github.com/excalidraw/excalidraw-mcp) — interactive diagram rendering
- [Architecture Review Agent Deployment Guide](deployment.md) — detailed RBAC and deployment walkthrough
- [Microsoft Foundry](https://ai.azure.com) - Microsoft Foundry is a unified platform designed for building, deploying, and managing AI applications and agents, integrating seamlessly with Azure services and tools. 

---

*Built with the Microsoft Agent Framework. Deployed on Microsoft Foundry. Diagrams powered by Excalidraw.*
