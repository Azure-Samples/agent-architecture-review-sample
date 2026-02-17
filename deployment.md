# Architecture Review Agent - Hosted Agent Deployment

Deploy the Architecture Review Agent as a **hosted agent** on Microsoft Foundry using the **VS Code Foundry extension** - the recommended deployment path for production use. This approach provides a stable, guided workflow with built-in validation, proper ACR integration, and simplified RBAC management.

> **Why use the extension?** The extension handles containerization, image building via ACR Tasks, deployment creation, and managed identity assignment automatically. It's more reliable than script-based approaches and provides step-by-step feedback during deployment.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **VS Code Extension** | [Microsoft Foundry for VS Code](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.vscode-ai-foundry) - **Install this first** |
| **Azure CLI** | v2.80+ - `az version` |
| **Python** | 3.11+ |
| **Foundry Project** | With a deployed model (e.g. `gpt-4.1`) |
| **Azure Login** | `az login` completed |

---

## Deployment Method - Foundry Extension (Recommended)

The VS Code Foundry extension provides the most stable and straightforward deployment experience. Follow these steps to deploy your agent.

### Step 1 - Install the Extension and Sign In

1. Install the [Microsoft Foundry for VS Code extension](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.vscode-ai-foundry)
2. Open this project in VS Code:
   ```bash
   code <path-to-agent-architecture-review-sample>
   ```
3. Open the **Microsoft Foundry** panel in the sidebar
4. Sign in with your Azure account - your Foundry workspace should appear in the tree view

### Step 2 - Deploy the Hosted Agent

1. Open the **Command Palette** (`Ctrl+Shift+P` or `Cmd+Shift+P` on Mac)
2. Run: **`Microsoft Foundry: Deploy Hosted Agent`**
3. **Select your target workspace** - choose the Foundry project where the agent will be deployed
4. **Select the container agent file** - point to `main.py` in this project
5. **Configure deployment parameters** - the extension reads `agent.yaml` for:
   - Agent name and description
   - Model deployment reference
   - Environment variables
6. **Wait for the deployment** - the extension will:
   - Package your source code
   - Upload to **Azure Container Registry (ACR)**
   - Build the container image remotely using ACR Tasks
   - Create a **hosted agent version** and **deployment** on Foundry
   - Assign a system-managed identity to the container
7. **Verify success** - the agent appears under **Hosted Agents (Preview)** in the Foundry extension tree view

![Extension Deployment Flow](docs/extension-deployment.png)

> **What happens behind the scenes:**
> - The extension creates an ACR build task with your Dockerfile
> - Container image is built in Azure (no local Docker required)
> - Managed identity is automatically assigned
> - Agent is registered in the Foundry Agent Service
> - Endpoint becomes available at `https://<your-resource>.services.ai.azure.com/api/projects/<your-project>/openai/responses`

### Step 3 - Verify in the Foundry Portal

1. Navigate to [Microsoft Foundry](https://ai.azure.com)
2. Open your project
3. Go to **Hosted Agents (Preview)**
4. Find your agent - status should show **Running**
5. Check container logs - should display:
   ```
   Architecture Review Agent Server running on http://localhost:8088
   ```

---

## Configure RBAC Permissions

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

# 2. Azure AI User - grants ALL Foundry data-plane actions
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

## Test the Deployed Agent

### Option A - Foundry Playground (in VS Code)

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

### Option B - REST API (curl / Invoke-RestMethod)

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

### Option C - Local testing (before deployment)

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
