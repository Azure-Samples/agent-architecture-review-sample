# Windows Scripts - Command Reference

This folder contains all PowerShell scripts for Windows development and deployment.

---

## 📋 Quick Command Reference

| Task | Command |
|------|---------|
| **First-time setup** | `.\scripts\windows\setup.ps1` |
| **Start dev server** | `.\scripts\windows\dev.ps1` |
| **Deploy web app** | `.\scripts\windows\deploy-webapp.ps1 -ResourceGroup arch-review-rg -AppName arch-review-web` |
| **Clean up resources** | `.\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg` |

---

## 🔧 Setup Script

### What It Does
- Creates Python virtual environment (`.venv`)
- Installs Python dependencies from `requirements.txt`
- Installs Node.js dependencies for React frontend
- Builds frontend (optional)

### Basic Usage
```powershell
cd C:\Users\YourName\agent-architecture-review-sample
.\scripts\windows\setup.ps1
```

### Example Output
```
✅ Creating virtual environment...
✅ Installing Python dependencies...
✅ Installing Node.js dependencies...
✅ Setup complete!

Next: Run .\scripts\windows\dev.ps1
```

### If Already Set Up
Safe to run multiple times-will update dependencies if needed.

---

## 🚀 Dev Server Script

### What It Does
- Activates Python virtual environment
- Starts FastAPI backend on `http://localhost:8000`
- Starts Vite React dev server on `http://localhost:5173`
- Frontend proxies API calls to backend

### Basic Usage
```powershell
.\scripts\windows\dev.ps1
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
```powershell
Ctrl+C  # Stops both FastAPI and Vite
```

---

##  Deploy Script — Web App

### What It Does
- Validates prerequisites
- Builds Docker container (multi-stage: Node + Python)
- Uploads to Azure Container Registry (ACR)
- Deploys to Azure App Service
- Configures networking and environment

### Deploy Web App
```powershell
.\scripts\windows\deploy-webapp.ps1 -ResourceGroup arch-review-rg -AppName arch-review-web
```

### Deploy Web App with Custom Options
```powershell
# Specify app name
.\scripts\windows\deploy-webapp.ps1 `
    -ResourceGroup arch-review-rg `
    -AppName my-reviewer

# Specify location
.\scripts\windows\deploy-webapp.ps1 `
    -ResourceGroup arch-review-rg `
    -AppName arch-review-web `
    -Location westus2
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
- Removes deployed web app resources
- Deletes container registry
- Deletes resource groups
- Cleans up all Azure resources

### ⚠️ WARNING: Non-Recoverable
This operation **CANNOT be undone**. Once executed, all Azure resources are deleted.

### Usage
```powershell
.\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg
```

### With Confirmation
Script will prompt before deleting:
```
❓ About to delete Azure resources. Continue? (Y/n)
```

### Example Output
```
🗑️ Cleaning up Azure resources...
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

### PowerShell: "cannot be loaded because running scripts is disabled"
```powershell
# Enable script execution for current user
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then re-run the script
.\scripts\windows\setup.ps1
```

### Setup: "venv already exists"
Safe to re-run-will update dependencies:
```powershell
.\scripts\windows\setup.ps1
```

Or start fresh:
```powershell
rm -r .venv
.\scripts\windows\setup.ps1
```

### Dev: "Port 8000 already in use"
Another process is using the port:
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID)
taskkill /PID <PID> /F
```

### Deploy: "Not authenticated"
Log in to Azure first:
```powershell
az login

# Verify subscription
az account show
```

### Deploy: "Resource group not found"
Create the resource group first:
```powershell
az group create `
    --name arch-review-rg `
    --location eastus2
```

---

## 📚 Full Workflow Example

### First-time Setup & Local Testing
```powershell
# 1. Setup environment (first time only)
.\scripts\windows\setup.ps1

# 2. Start dev server locally
.\scripts\windows\dev.ps1

# 3. Open browser to http://localhost:5173
# 4. Test the web UI
# 5. Press Ctrl+C to stop dev server
```

### Deploy to Azure
```powershell
# 1. Ensure you're logged in
az login

# 2. Create resource group (or use existing)
az group create --name arch-review-rg --location eastus2

# 3. Deploy web app
.\scripts\windows\deploy-webapp.ps1 `
    -ResourceGroup arch-review-rg `
    -AppName arch-review-web

# 4. Wait for deployment to complete
# 5. Web app available at azurewebsites.net URL
```

### Clean Up
```powershell
# Delete everything
.\scripts\windows\teardown.ps1
```

---

## 🔗 Related Documentation

- [../README.md](../README.md) - Scripts overview & quick reference
- [../../README.md](../../README.md) - Full repository guide
- [../../docs/deployment.md](../../docs/deployment.md) - Hosted agent deployment (VS Code Foundry extension)
- [../../run_local.py](../../run_local.py) - CLI testing alternative

---

## ✅ Quick Checklist

- [ ] Run `.\scripts\windows\setup.ps1` (installs dependencies + Foundry extension)
- [ ] Run `.\scripts\windows\dev.ps1` to test locally
- [ ] Open http://localhost:5173 to see web UI
- [ ] **For Web App:** Run `.\scripts\windows\deploy-webapp.ps1 -ResourceGroup arch-review-rg -AppName arch-review-web`
- [ ] **For Hosted Agent:** Use VS Code Command Palette (`Ctrl+Shift+P`) → `Microsoft Foundry: Deploy Hosted Agent`
- [ ] Use `.\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg` to clean up
