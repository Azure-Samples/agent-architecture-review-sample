# Scripts — Choose Your OS

This folder contains all setup, development, and deployment scripts. Choose the path that matches your OS.

---

## 🐧 **Linux / macOS (Bash)**

If you're using Linux or macOS, see [linux-mac/README.md](linux-mac/README.md) for detailed command reference.

### Quick Start
```bash
bash scripts/linux-mac/setup.sh                    # Setup (first time only)
bash scripts/linux-mac/dev.sh                      # Start dev server
bash scripts/linux-mac/deploy.sh --target agent   # Deploy agent
bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg  # Cleanup
```

**📖 For detailed commands, options, and troubleshooting:** See [linux-mac/README.md](linux-mac/README.md)

---

## 🪟 **Windows (PowerShell)**

If you're using Windows, see [windows/README.md](windows/README.md) for detailed command reference.

### Quick Start
```powershell
.\scripts\windows\setup.ps1          # Setup (first time only)
.\scripts\windows\dev.ps1             # Start dev server
.\scripts\windows\deploy.ps1 -target agent    # Deploy agent
.\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg  # Cleanup
```

**📖 For detailed commands, options, and troubleshooting:** See [windows/README.md](windows/README.md)

---

## 🎯 Quick Reference

| Task | Windows | Linux/macOS |
|------|---------|-----------|
| **Setup** | `.\scripts\windows\setup.ps1` | `bash scripts/linux-mac/setup.sh` |
| **Dev Server** | `.\scripts\windows\dev.ps1` | `bash scripts/linux-mac/dev.sh` |
| **Deploy Agent** | `.\scripts\windows\deploy.ps1 -target agent` | `bash scripts/linux-mac/deploy.sh --target agent` |
| **Deploy Webapp** | `.\scripts\windows\deploy.ps1 -target webapp` | `bash scripts/linux-mac/deploy.sh --target webapp` |
| **Cleanup** | `.\scripts\windows\teardown.ps1 -ResourceGroup arch-review-rg` | `bash scripts/linux-mac/teardown.sh --resource-group arch-review-rg` |

---

## 🚀 For CLI Testing (Works Anywhere)

To test the agent locally without setup scripts:

```bash
python run_local.py examples/ecommerce.yaml
python run_local.py examples/event_driven.md
python run_local.py --text "API Gateway -> Auth Service -> User DB"
```

No Azure required for structured inputs!

---

## 📚 Learn More

- [README.md](../README.md) — Project overview
- [deployment.md](../deployment.md) — Detailed Azure deployment
- [blog_post.md](../blog_post.md) — Architecture review story
