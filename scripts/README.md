# Scripts - Choose Your OS

This folder contains all setup, development, and deployment scripts for the [Architecture Review Agent](https://github.com/Azure-Samples/agent-architecture-review-sample). Choose the path that matches your OS.

---

## Three Ways to Use This Agent

1. **Local Development** - Run the web UI locally for testing (`dev` script)
2. **Web App Deployment** - Deploy to Azure App Service with React UI (`deploy-webapp` script)
3. **Hosted Agent Deployment** - Deploy to Microsoft Foundry via VS Code extension (installed by `setup` script)

---

## 🐧 **Linux / macOS (Bash)**

If you're using Linux or macOS, see [linux-mac/README.md](linux-mac/README.md) for detailed command reference.

### Quick Start
```bash
bash scripts/linux-mac/setup.sh      # Setup: installs dependencies + Microsoft Foundry VS Code extension
bash scripts/linux-mac/dev.sh        # Start local dev server (Web UI)
bash scripts/linux-mac/deploy-webapp.sh --resource-group arch-review-rg --app-name arch-review-web  # Deploy web app to Azure
bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg  # Cleanup Azure resources
```

**For Hosted Agent Deployment:** After running setup, use **VS Code Command Palette** → `Microsoft Foundry: Deploy Hosted Agent`

**📖 For detailed commands, options, and troubleshooting:** See [linux-mac/README.md](linux-mac/README.md)

---

## 🪟 **Windows (PowerShell)**

If you're using Windows, see [windows/README.md](windows/README.md) for detailed command reference.

### Quick Start
```powershell
.\scripts\windows\setup.ps1          # Setup: installs dependencies + Microsoft Foundry VS Code extension
.\scripts\windows\dev.ps1             # Start local dev server (Web UI)
.\scripts\windows\deploy-webapp.ps1 -ResourceGroup arch-review-rg -AppName arch-review-web  # Deploy web app to Azure
.\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg  # Cleanup Azure resources
```

**For Hosted Agent Deployment:** After running setup, use **VS Code Command Palette** (`Ctrl+Shift+P`) → `Microsoft Foundry: Deploy Hosted Agent`

**📖 For detailed commands, options, and troubleshooting:** See [windows/README.md](windows/README.md)

---

## 🎯 Quick Reference

| Task | Windows | Linux/macOS |
|------|---------|-----------|
| **Setup** | `.\scripts\windows\setup.ps1` | `bash scripts/linux-mac/setup.sh` |
| **Local Dev Server** | `.\scripts\windows\dev.ps1` | `bash scripts/linux-mac/dev.sh` |
| **Deploy Web App** | `.\scripts\windows\deploy-webapp.ps1 -ResourceGroup <rg> -AppName <name>` | `bash scripts/linux-mac/deploy-webapp.sh --resource-group <rg> --app-name <name>` |
| **Deploy Hosted Agent** | VS Code: `Ctrl+Shift+P` → `Microsoft Foundry: Deploy Hosted Agent` | VS Code: `Cmd+Shift+P` → `Microsoft Foundry: Deploy Hosted Agent` |
| **Cleanup** | `.\scripts\windows\teardown.ps1 -ResourceGroup <rg>` | `bash scripts/linux-mac/teardown.sh --resource-group <rg>` |

> **Note:** The setup script automatically installs the Microsoft Foundry VS Code extension for hosted agent deployment.

---

## 🚀 Alternative: CLI Testing (No Web UI)

To test the agent logic directly via command line (no setup scripts needed):

```bash
python run_local.py examples/ecommerce.yaml
python run_local.py examples/event_driven.md
python run_local.py --text "API Gateway -> Auth Service -> User DB"
```

> **Note:** CLI mode works without Azure for structured inputs. For unstructured inputs requiring LLM inference, configure Azure OpenAI credentials in `.env`.

---

## 📚 Learn More

- [README.md](../README.md) - Project overview & all deployment options
- [deployment.md](../docs/deployment.md) - Hosted agent deployment guide (Microsoft Foundry)
- [windows/README.md](windows/README.md) - Windows scripts detailed reference
- [linux-mac/README.md](linux-mac/README.md) - Linux/macOS scripts detailed reference
