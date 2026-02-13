# Architecture Review Agent — Hosted Agent Deployment

Deploy the Architecture Review Agent as a **hosted agent** on Azure AI Foundry using the
VS Code Foundry extension. No local Docker installation required.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **VS Code Extension** | [Microsoft Foundry for VS Code](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.vscode-ai-foundry) |
| **Azure CLI** | v2.80+ — `az version` |
| **Python** | 3.11+ |
| **Foundry Project** | With a deployed model (e.g. `gpt-4.1`) |
| **Azure Login** | `az login` completed |

---

## 1. Deploy Using the Foundry Extension

### Step 1 — Open the project in VS Code

```
code <path-to-agent-architecture-review-sample>
```

### Step 2 — Sign in to Azure

Open the **Microsoft Foundry** panel in the sidebar and sign in with your
Azure account. Your Foundry workspace should appear in the tree view.

### Step 3 — Deploy the hosted agent

1. Open the **Command Palette** (`Ctrl+Shift+P`).
2. Run: **`Microsoft Foundry: Deploy Hosted Agent`**.
3. **Select your target workspace** — pick the Foundry project where the
   agent will be deployed (e.g. `arch-review`).
4. **Select the container agent file** — point to `main.py`.
5. **Configure deployment parameters** — the extension reads `agent.yaml`
   for the agent definition (name, model, env vars, cpu/memory).
6. Wait for the build to complete — the extension:
   - Uploads your source code to **Azure Container Registry** (ACR).
   - Builds the container image remotely using ACR Tasks.
   - Creates a **hosted agent version** and **deployment** on Foundry.
7. On success, the agent appears under **Hosted Agents (Preview)** in
   the Foundry extension tree view.

### Step 4 — Verify in the Foundry portal

- Status should show **Running**.
- Container logs should show:
  ```
  Architecture Review Agent Server running on http://localhost:8088
  ```

---

## 2. Assign Required RBAC Roles

The hosted agent container runs with a **system-assigned managed identity**.
This identity needs permissions to call the Foundry Agent API (`create_agent`).

### Find the managed identity principal ID

After deployment, the principal ID is visible in the Foundry portal under
the agent's **Details** tab, or in the error message if permissions are
missing.

### Assign roles via Azure CLI

```powershell
# 1. Get the Foundry account resource ID
$scope = (az cognitiveservices account list `
  --query "[?name=='<your-resource>'].id" -o tsv)

# 2. Azure AI User — grants ALL Foundry data-plane actions
#    (includes Microsoft.CognitiveServices/accounts/AIServices/agents/write)
az role assignment create `
  --assignee "<PRINCIPAL_ID>" `
  --role "Azure AI User" `
  --scope $scope

# 3. Also assign at the project scope
az role assignment create `
  --assignee "<PRINCIPAL_ID>" `
  --role "Azure AI User" `
  --scope "$scope/projects/<your-project>"
```

Replace `<PRINCIPAL_ID>` with the managed identity's Object ID.

### Role reference

| Role | Scope | Purpose |
|---|---|---|
| **Azure AI User** | Account + Project | All data-plane actions (`agents/write`, `agents/read`, model inference) |
| **Container Registry Repository Reader** | ACR | Pull container images (auto-assigned by the extension) |

> **Note:** RBAC propagation can take up to **10 minutes**. Wait before
> testing after assigning roles.

### Verify assignments

```powershell
az role assignment list `
  --assignee "<PRINCIPAL_ID>" `
  --all `
  --query "[].{role:roleDefinitionName, scope:scope}" `
  -o table
```

---

## 3. Test the Deployed Agent

### Option A — Foundry Playground (in VS Code)

1. In the Foundry extension tree view, expand **Hosted Agents (Preview)**.
2. Click on **Architecture Review Agent**.
3. Open the **Playground** tab.
4. Send a test prompt:
   ```
   Review this architecture:
   Client -> API Gateway -> Auth Service
   API Gateway -> Product Service -> PostgreSQL
   API Gateway -> Order Service -> PostgreSQL
   Order Service -> Payment Gateway
   ```
5. The agent should return a full review with risks, components, and
   diagram info.

### Option B — REST API (curl / Invoke-RestMethod)

The deployed agent exposes the **OpenAI Responses API**:

```powershell
$endpoint = "https://<your-resource>.services.ai.azure.com/api/projects/<your-project>"
$token = (az account get-access-token --resource "https://cognitiveservices.azure.com" --query accessToken -o tsv)

Invoke-RestMethod `
  -Uri "$endpoint/openai/responses?api-version=2025-05-15-preview" `
  -Method POST `
  -Headers @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
  } `
  -Body (@{
    input = @{
      messages = @(
        @{ role = "user"; content = "Review: LB -> API -> Cache -> DB" }
      )
    }
  } | ConvertTo-Json -Depth 5)
```

### Option C — Local testing (before deployment)

Run the agent locally without Docker:

```powershell
cd <path-to-agent-architecture-review-sample>
.\.venv\Scripts\Activate.ps1
python main.py
```

Then hit the local endpoint:

```powershell
Invoke-RestMethod -Uri "http://localhost:8088/responses" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"input":{"messages":[{"role":"user","content":"Review: LB -> API -> DB"}]}}'
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| **ACR build fails: `Dockerfile not found`** | Ensure `Dockerfile` is NOT in `.dockerignore` |
| **PermissionDenied: `agents/write`** | Assign **Azure AI User** at account + project scope (see Section 2) |
| **RBAC still failing after assignment** | Wait 10 min for propagation; verify with `az role assignment list` |
| **Container starts but agent errors** | Check container logs in Foundry portal for Python exceptions |
| **Model not found** | Verify `MODEL_DEPLOYMENT_NAME` env var matches your deployed model name |

---