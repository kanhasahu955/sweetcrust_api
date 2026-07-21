# GitHub Actions → Hostinger (backend_v2 only)

Deploys **only this backend** (`backend_v2`). No admin, mobile, or other apps.

Workflow: [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)

| Trigger | When |
|---------|------|
| `push` to `main` / `master` | Any commit in this repo |
| `workflow_dispatch` | Manual run (optional skip rebuild) |

```mermaid
flowchart LR
  Push[push_main] --> GHA[GitHub_Actions]
  GHA --> SSH[SSH_rsync]
  SSH --> VPS[Hostinger_VPS]
  VPS --> Compose[docker_compose_up]
  Compose --> Health[gateway_health]
```

## 0. Create a GitHub repo from `backend_v2` only

```bash
cd /Users/ashok-sahu/my_applications/bakerywala_2026/backend_v2
git init -b main
git add .
git commit -m "backend_v2 production + Hostinger CI/CD"
gh repo create sweetcrust-backend-v2 --private --source=. --remote=origin --push
# or: git remote add origin git@github.com:YOU/sweetcrust-backend-v2.git && git push -u origin main
```

Repo root = `backend_v2` (contains `.github/workflows/deploy.yml`, `docker-compose.prod.yml`, `deploy/`).

## 1. Deploy SSH key

```bash
ssh-keygen -t ed25519 -C "github-actions-hostinger" -f ~/.ssh/hostinger_gha -N ""
ssh-copy-id -i ~/.ssh/hostinger_gha.pub root@145.223.21.127
```

## 2. GitHub secrets

Repo → **Settings → Secrets and variables → Actions**:

| Secret | Example |
|--------|---------|
| `HOSTINGER_HOST` | `145.223.21.127` |
| `HOSTINGER_USER` | `root` |
| `HOSTINGER_SSH_KEY` | Full private key from `~/.ssh/hostinger_gha` |
| `HOSTINGER_SSH_PORT` | `22` (optional) |

Keep `.env.production` **on the VPS only** — not in GitHub.

## 3. One-time on the VPS

```bash
bash deploy/hostinger/setup-vps.sh   # if Docker missing
# After first deploy sync:
cd /opt/sweetcrust/backend_v2
cp .env.production.example .env.production
nano .env.production                 # fill secrets
./deploy/hostinger/issue-cert.sh     # TLS for api.bakerywala.cloud
```

## 4. Day-to-day

```bash
cd backend_v2
git add -A && git commit -m "…" && git push origin main
```

Actions → **Deploy** runs rsync + `docker compose up -d --build` + health check.

Manual: Actions → **Deploy** → **Run workflow**.
