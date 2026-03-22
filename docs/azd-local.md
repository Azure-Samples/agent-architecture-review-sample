# End-to-end AZD tutorial (install, setup, run, invoke)

This guide is the complete `azd` path for this repository:

1. Install tooling
2. Configure environment
3. Run hosted agent locally
4. Invoke locally
5. (Optional) provision/deploy to Azure

> Scope: Hosted-agent flow with `azd`.
> If you want the engine-only flow, use `python run_local.py ...` instead.

> Looking for all project docs in one place? See the [Documentation Index](README.md).

## 0) What this tutorial validates

By the end, you should be able to:

- start the local hosted-agent runtime with `azd ai agent run`
- invoke the **Architecture Review Agent** with a real architecture description and receive a structured risk report + Excalidraw diagram
- pass a YAML/Markdown scenario file inline or describe an architecture in plain text
- verify environment wiring via `azd env get-values`

## 1) Install prerequisites (Windows)

### 1.1 Install AZD

Use winget (Microsoft Learn recommended for Windows):

```powershell
winget install microsoft.azd
```

Verify installation:

```powershell
azd version
```

### 1.2 Install Azure CLI (if needed)

```powershell
winget install Microsoft.AzureCLI
```

Verify:

```powershell
az version
```

### 1.3 Install the AZD AI Agents extension

This repo requires the extension declared in `azure.yaml` (`azure.ai.agents`).

```powershell
azd extension install azure.ai.agents
```

Check installed extensions:

```powershell
azd extension list --installed
```

## 2) Prepare this repository locally

From repo root (`agent-architecture-review-sample`):

### 2.0 Initialize AZD project context (`azd init`)

If you cloned this repo as-is (it already includes `azure.yaml`), you can usually skip `azd init` and go straight to environment setup.

If you're adapting this into a new repo or want AZD to (re)initialize project metadata, run:

```powershell
azd init
```

Or for code-first discovery in a custom project:

```powershell
azd init --from-code
```

### What AZD auto-generates

After `azd init` / `azd env new` / `azd provision`, AZD creates local project metadata folders and files, including:

- `.azure/`
- `.azure/<environment-name>/config.json`
- `.azure/<environment-name>/.env`

These hold environment selection and resolved environment values used by commands like `azd env get-values`, `azd ai agent run`, and `azd deploy`.

> Keep secrets safe: review `.gitignore` and avoid committing sensitive environment values.

### 2.1 Create/activate Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2.2 Install Python dependencies

```powershell
pip install -r requirements.txt
```

## 3) Authenticate and configure AZD environment

### 3.1 Login

You can use either Azure CLI or AZD login (both are valid):

```powershell
az login
```

or

```powershell
azd auth login
```

### 3.2 Select/create AZD environment

If environment already exists:

```powershell
azd env list
azd env select <environment-name>
```

If you need a new environment:

```powershell
azd env new <environment-name>
```

### 3.3 Confirm required environment values

Dump active values:

```powershell
azd env get-values
```

At minimum, ensure these are present for hosted-agent local run:

- `AZURE_AI_PROJECT_ENDPOINT`
- `AZURE_AI_MODEL_DEPLOYMENT_NAME`

Optional (interactive diagram MCP provider):

- `ARCH_REVIEW_MCP_PROVIDER` = `excalidraw` or `drawio`
- `EXCALIDRAW_MCP_URL` (if using Excalidraw)
- `DRAWIO_MCP_URL` and `DRAWIO_MCP_TOOL` (if using Draw.io)

If missing, set them in active env:

```powershell
azd env set AZURE_AI_PROJECT_ENDPOINT "<your-project-endpoint>"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<your-model-deployment-name>"
```

## 4) Run locally with AZD (hosted-agent path)

### 4.1 Start local hosted-agent runtime

Open terminal #1:

```powershell
azd ai agent run
```

What this does in this repo:

- reads `azure.yaml`
- starts hosted-agent service
- uses `python main.py` startup command

### 4.2 Invoke from a second terminal

Open terminal #2.  The agent understands **any input format** and handles all preprocessing internally:

- **Pass a file path** — the agent reads the file automatically (YAML, Markdown, plain text).
- **Pass inline text** — arrow notation, prose, or any description works as-is.
- **Prefixes are optional** — `"Review my architecture: "` is stripped automatically; you can omit it entirely.

#### Option A — YAML scenario file (pass the path directly)

```powershell
azd ai agent invoke --local "scenarios/ecommerce.yaml"
```

#### Option B — Inline plain-text description

```powershell
azd ai agent invoke --local "LB -> 3 API servers -> PostgreSQL primary with read replica -> Redis cache"
```

#### Option C — Markdown scenario file (pass the path directly)

```powershell
azd ai agent invoke --local "scenarios/event_driven.md"
```

Expected result for any of the above:

- structured JSON report with executive summary, risk table, component map, and diagram info
- Excalidraw file written to `output/architecture_<run_id>.excalidraw` (unique per invocation)
- PNG diagram written to `output/architecture_<run_id>.png` (unique per invocation)
- non-error exit code from invoke command

> **Tip:** For repeated local testing without the hosted-agent runtime, use `python run_local.py scenarios/ecommerce.yaml` instead — it runs the same pipeline but bypasses the agent layer.

## 5) Troubleshooting checklist

### Issue: `invoke --local` fails

Run these checks in order:

```powershell
azd env get-values
azd auth status
```

Verify:

1. Correct environment is selected (`azd env select ...`)
2. `AZURE_AI_PROJECT_ENDPOINT` is valid for your Foundry project
3. `AZURE_AI_MODEL_DEPLOYMENT_NAME` exists in that project
4. You restarted `azd ai agent run` after env changes

### Issue: startup error about missing endpoint

`main.py` intentionally fails fast when endpoint is absent.

Set one of:

- `AZURE_AI_PROJECT_ENDPOINT` (preferred)
- `PROJECT_ENDPOINT` (fallback)

## 6) Optional: deploy/provision with AZD

If you want cloud deployment beyond local testing:

```powershell
azd provision
azd deploy
```

Or combined flow:

```powershell
azd up
```

> Tip: run `azd show` to inspect project/resource state.

## 7) Local mode cheat sheet

- **Engine-local (no hosted runtime, structured inputs):**
  - `python run_local.py scenarios/ecommerce.yaml`
  - `python run_local.py scenarios/event_driven.md`
  - `python run_local.py --text "LB -> 3 API servers -> PostgreSQL"`
  - `python run_local.py README.md --infer` (force LLM inference)
- **Hosted-agent-local (AZD runtime, full agent loop):**
  - `azd ai agent run`  ← terminal 1
  - `azd ai agent invoke --local "scenarios/ecommerce.yaml"` ← terminal 2
  - `azd ai agent invoke --local "scenarios/event_driven.md"`
  - `azd ai agent invoke --local "LB -> 3 API servers -> PostgreSQL -> Redis"`
  - Each run writes unique `output/architecture_<run_id>.excalidraw` and `.png` files

## 8) References

### AZD (official)

- Install/update AZD: https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd
- AZD command reference: https://learn.microsoft.com/azure/developer/azure-developer-cli/reference

### Microsoft Foundry / hosted agents

- Hosted agents concepts: https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry
- Agent runtime components: https://learn.microsoft.com/azure/ai-foundry/agents/concepts/runtime-components?view=foundry
- Publish agents to Microsoft 365 Copilot and Teams (scope model): https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/publish-copilot

### This repository

- Main project guide: [README.md](../README.md)
- Hosted agent deployment guide: [deployment.md](deployment.md)
- Full docs map: [docs/README.md](README.md)