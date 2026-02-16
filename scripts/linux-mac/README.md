# Linux/macOS Scripts — Command Reference

This folder contains all Bash scripts for Linux and macOS development and deployment.

---

## 📋 Quick Command Reference

| Task | Command |
|------|---------|
| **First-time setup** | `bash scripts/linux-mac/setup.sh` |
| **Start dev server** | `bash scripts/linux-mac/dev.sh` |
| **Deploy hosted agent** | `bash scripts/linux-mac/deploy.sh --target agent` |
| **Deploy web app** | `bash scripts/linux-mac/deploy.sh --target webapp --resource-group arch-review-rg --app-name arch-review-web` |
| **Clean up resources** | `bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg` |

---

## 🔧 Setup Script

### What It Does
- Creates Python virtual environment (`.venv`)
- Installs Python dependencies from `requirements.txt`
- Installs Node.js dependencies for React frontend
- Builds frontend (optional)

### Basic Usage
```bash
cd ~/agent-architecture-review-sample
bash scripts/linux-mac/setup.sh
```

### With Verbose Output
```bash
bash -x scripts/linux-mac/setup.sh
```

### Example Output
```
✅ Creating virtual environment...
✅ Installing Python dependencies...
✅ Installing Node.js dependencies...
✅ Setup complete!

Next: Run bash scripts/linux-mac/dev.sh
```

### If Already Set Up
Safe to run multiple times—will update dependencies if needed.

---

## 🚀 Dev Server Script

### What It Does
- Activates Python virtual environment
- Starts FastAPI backend on `http://localhost:8000`
- Starts Vite React dev server on `http://localhost:5173`
- Frontend proxies API calls to backend

### Basic Usage
```bash
bash scripts/linux-mac/dev.sh
```

### Example Output
```
✅ Activating virtual environment...
✅ Starting FastAPI backend (port 8000)...
✅ Starting Vite frontend (port 5173)...

Open browser: http://localhost:5173

Press Ctrl+C to stop both servers
```

### Accessing the App
- **Frontend (React UI):** http://localhost:5173
- **Backend (API):** http://localhost:8000/docs (Swagger UI)
- **Configuration:** Frontend talks to backend automatically

### Stopping the Server
```bash
Ctrl+C  # Stops both FastAPI and Vite
```

### Running in Background
```bash
# Start and detach
nohup bash scripts/linux-mac/dev.sh > dev.log 2>&1 &

# Check if running
ps aux | grep "dev.sh"

# View logs
tail -f dev.log
```

---

## 🌩️ Deploy Script — Hosted Agent

### What It Does
- Validates Azure login
- Builds Docker container
- Uploads to Azure Container Registry (ACR)
- Deploys as Hosted Agent to Microsoft Foundry
- Configures managed identity and RBAC

### Prerequisites
- `az login` completed
- Azure subscription selected
- Access to target resource group

### Deploy to Hosted Agent (Default)
```bash
bash scripts/linux-mac/deploy.sh --target agent --resource-group arch-review-rg
```

### Deploy with Custom Options
```bash
# Specify project name
bash scripts/linux-mac/deploy.sh \
    --target agent \
    --resource-group arch-review-rg \
    --project-name my-arch-review

# Specify location
bash scripts/linux-mac/deploy.sh \
    --target agent \
    --resource-group arch-review-rg \
    --location westus2

# Specify model
bash scripts/linux-mac/deploy.sh \
    --target agent \
    --resource-group arch-review-rg \
    --model-name gpt-4.1
```

### Deploy Parameters
```bash
# --target agent
  Required when deploying hosted agent
  
# --resource-group STRING
  Azure resource group name
  Example: "arch-review-rg"
  
# --project-name STRING
  Microsoft Foundry project name (default: "arch-review")
  Example: "my-project"
  
# --location STRING
  Azure region (default: "eastus2")
  Example: "westus2", "eastus", "northeurope"
  
# --model-name STRING
  Model to deploy (default: "gpt-4.1")
  Example: "gpt-4.1"
```

### Example Output
```
🚀 Deploying Hosted Agent...
✅ Logged in to Azure
✅ Building Docker image...
✅ Pushing to ACR...
✅ Creating AI Services account...
✅ Creating Microsoft Foundry project...
✅ Deploying model...
✅ Deploying agent...
✅ Configuring RBAC...

✅ Deployment successful!

Agent endpoint: https://arch-review-agent.azurewebsites.net/
```

### After Deployment
- Agent available in Microsoft Foundry portal
- Can publish to Teams, M365 Copilot, or stable endpoint
- Use `/responses` endpoint for API calls

---

## 🌐 Deploy Script — Web App

### What It Does
- Validates prerequisites
- Builds Docker container (multi-stage: Node + Python)
- Uploads to Azure Container Registry (ACR)
- Deploys to Azure App Service
- Configures networking and environment

### Deploy Web App
```bash
bash scripts/linux-mac/deploy.sh --target webapp --resource-group arch-review-rg --app-name arch-review-web
```

### Deploy Web App with Custom Options
```bash
# Specify app name
bash scripts/linux-mac/deploy.sh \
    --target webapp \
    --resource-group arch-review-rg \
    --app-name my-reviewer

# Specify location
bash scripts/linux-mac/deploy.sh \
    --target webapp \
    --resource-group arch-review-rg \
    --app-name arch-review-web \
    --location westus2
```

### Example Output
```
🚀 Deploying Web App...
✅ Building container (Node + Python multi-stage)...
✅ Pushing to ACR...
✅ Creating App Service Plan...
✅ Deploying container to App Service...
✅ Configuring environment variables...

✅ Deployment successful!

Web app: https://arch-review-app.azurewebsites.net/
```

### After Deployment
- Web app available at Azure App Service URL
- React UI at root (`/`)
- REST API endpoints at `/api/*`
- Can be accessed from browser immediately

---

## 🗑️ Teardown Script

### What It Does
- Removes deployed hosted agent or web app
- Deletes container registry
- Deletes resource groups
- Cleans up all Azure resources

### ⚠️ WARNING: Non-Recoverable
This operation **CANNOT be undone**. Once executed, all Azure resources are deleted.

### Usage
```bash
bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg
```

### With Confirmation
Script will prompt before deleting:
```
❓ About to delete Azure resources. Continue? (y/n)
```

### Example Output
```
🗑️ Cleaning up Azure resources...
✅ Deleting hosted agent...
✅ Deleting container registry...
✅ Deleting resource groups...

✅ Cleanup complete!
```

### Before Running
- Ensure you want to delete everything
- Backup any data you need
- Verify the resource group name

---

## 🛠️ Troubleshooting

### Setup: "venv already exists"
Safe to re-run—will update dependencies:
```bash
bash scripts/linux-mac/setup.sh
```

Or start fresh:
```bash
rm -rf .venv
bash scripts/linux-mac/setup.sh
```

### Setup: "Command not found: node"
Node.js not installed or not in PATH:
```bash
# macOS
brew install node

# Ubuntu/Debian
sudo apt-get install nodejs npm

# Then re-run setup
bash scripts/linux-mac/setup.sh
```

### Dev: "Port 8000 already in use"
Another process is using the port:
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process (replace PID)
kill -9 <PID>
```

### Dev: "Port 5173 already in use"
Clean up old Vite processes:
```bash
# Find and kill Vite
pkill -f "vite"
```

### Deploy: "Not authenticated"
Log in to Azure first:
```bash
az login

# Verify subscription
az account show
```

### Deploy: "Resource group not found"
Create the resource group first:
```bash
az group create \
    --name arch-review-rg \
    --location eastus2
```

### Deploy: "Docker not found"
Install Docker first:
```bash
# macOS
brew install docker

# Ubuntu/Debian
sudo apt-get install docker.io

# Start Docker daemon
sudo systemctl start docker
```

### Permission Denied on Script
Make scripts executable:
```bash
chmod +x scripts/linux-mac/setup.sh
chmod +x scripts/linux-mac/dev.sh
chmod +x scripts/linux-mac/deploy.sh
chmod +x scripts/linux-mac/teardown.sh

# Then try again
bash scripts/linux-mac/setup.sh
```

---

## 📚 Full Workflow Example

### First-time Setup & Local Testing
```bash
# 1. Setup environment (first time only)
bash scripts/linux-mac/setup.sh

# 2. Start dev server locally
bash scripts/linux-mac/dev.sh

# 3. Open browser to http://localhost:5173
# 4. Test the web UI
# 5. Press Ctrl+C to stop dev server
```

### Deploy to Azure
```bash
# 1. Ensure you're logged in
az login

# 2. Create resource group (or use existing)
az group create \
    --name arch-review-rg \
    --location eastus2

# 3. Deploy hosted agent
bash scripts/linux-mac/deploy.sh \
    --target agent \
    --resource-group arch-review-rg

# 4. Wait for deployment to complete
# 5. Agent appears in Microsoft Foundry portal
```

### Clean Up
```bash
# Delete everything
bash scripts/linux-mac/teardown.sh
```

---

## 🔗 Related Documentation

- [../README.md](../README.md) — Project overview
- [../../README.md](../../README.md) — Full repository guide
- [../../deployment.md](../../deployment.md) — Detailed deployment steps
- [../../run_local.py](../../run_local.py) — CLI testing alternative

---

## ✅ Quick Checklist

- [ ] Run `bash scripts/linux-mac/setup.sh` (first time only)
- [ ] Run `bash scripts/linux-mac/dev.sh` to test locally
- [ ] Open http://localhost:5173 to see UI
- [ ] Run Azure deployment with `bash scripts/linux-mac/deploy.sh --target agent`
- [ ] Verify agent in Azure portal
- [ ] Use `bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg` when done
