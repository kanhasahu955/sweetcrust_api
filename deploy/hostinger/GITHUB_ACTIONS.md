# Step-by-step: GitHub → Hostinger VPS (backend_v2)

Repo: https://github.com/kanhasahu955/sweetcrust_api  
VPS: `145.223.21.127` (`srv1458436.hstgr.cloud`)  
API folder on server: `/opt/sweetcrust/backend_v2`  
Public URL: `https://api.bakerywala.cloud`

```text
You (code) → git push main → GitHub Actions → SSH/rsync → VPS folder → Docker Compose → API live
```

---

## Part A — One-time Hostinger setup

### A1. VPS is running
hPanel → **VPS** → `srv1458436` → status **Running**.

### A2. Firewall
hPanel → VPS → **Security → Firewall** → create/sync rules:

| Action | Protocol | Port | Source |
|--------|----------|------|--------|
| Accept | TCP | 22 | Anywhere |
| Accept | TCP | 80 | Anywhere |
| Accept | TCP | 443 | Anywhere |
| Drop | Any | Any | Anywhere |

Click **Synchronize** and wait until it finishes.

### A3. SSH key for GitHub deploy
On your Mac (once):

```bash
ssh-keygen -t ed25519 -C "github-actions-hostinger" -f ~/.ssh/hostinger_gha -N ""
cat ~/.ssh/hostinger_gha.pub
```

On Hostinger:
1. VPS → **SSH keys** → add that **public** key (`.pub` line), **or**
2. Open **Terminal** and run:

```bash
mkdir -p /root/.ssh && chmod 700 /root/.ssh
echo 'PASTE_YOUR_hostinger_gha.pub_LINE_HERE' >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

### A4. API folder (optional — deploy also creates it)

```bash
mkdir -p /opt/sweetcrust/backend_v2
cd /opt/sweetcrust/backend_v2
```

---

## Part B — One-time GitHub secrets

### B1. Install GitHub CLI and login (once)

```bash
brew install gh
gh auth login
```

### B2. Upload your full local `.env` (recommended)

Takes **all** keys from `backend_v2/.env`, applies production overrides
(`ENV=production`, Docker MySQL/Redis, `AUTH_PUBLIC_BASE_URL`, clears `OTP_DEV_CODE`,
adds `MYSQL_*` if missing), and stores the result as one GitHub secret:

```bash
cd backend_v2
chmod +x deploy/hostinger/sync-env-to-github.sh
./deploy/hostinger/sync-env-to-github.sh
# or: make secrets-sync-env CERTBOT_EMAIL=you@example.com
# or: ./deploy/hostinger/sync-env-to-github.sh --src=.env --email=you@example.com
```

| Secret | Source |
|--------|--------|
| `HOSTINGER_ENV_FILE` | full production env (all keys from your `.env`) |

Also keep SSH secrets (`HOSTINGER_HOST`, `HOSTINGER_USER`, `HOSTINGER_SSH_KEY`).

Re-run the sync script whenever you change local `.env` and want production updated.

### B2b. Alternative: generate only required secrets

```bash
cd backend_v2
./deploy/hostinger/bootstrap-github-secrets.sh --email you@example.com
```

This sets on GitHub (repo `kanhasahu955/sweetcrust_api`):

| Secret | Source |
|--------|--------|
| `HOSTINGER_HOST` / `HOSTINGER_USER` | defaults |
| `HOSTINGER_SSH_KEY` | `~/.ssh/hostinger_gha` |
| `MYSQL_ROOT_PASSWORD` / `MYSQL_PASSWORD` / `JWT_SECRET_KEY` | random (openssl) |
| `CERTBOT_EMAIL` | `--email` |

Rotate later: `./deploy/hostinger/bootstrap-github-secrets.sh --email you@example.com --force`  
(only if you also reset MySQL volume — rotating DB password breaks existing DB.)

Optional API keys (manual in GitHub UI): `GROQ_API_KEY`, `RAZORPAY_*`, etc.

### B3. How deploy uses them (automatic)

On every `git push origin main`, Actions:

1. Reads secrets → `render-env.sh` → builds `.env.production`
2. Uploads that file to `/opt/sweetcrust/backend_v2/.env.production`
3. Runs `docker compose up -d --build`

You never keep a production `.env` on your Mac.

### B4. Confirm workflow exists
File: `.github/workflows/deploy.yml` — trigger **push to `main`**.

---

## Part C — Everyday work (this is the loop)

### C1. Change code on your machine

```bash
cd /path/to/backend_v2
# edit files…
```

### C2. Commit and push to main

```bash
git add -A
git status
git commit -m "Describe your change"
git push origin main
```

### C3. Watch deploy
GitHub → **Actions** → workflow **Deploy** → open the latest run (green = OK).

What it does automatically:
1. Builds `.env.production` from GitHub secrets  
2. Copies code to `/opt/sweetcrust/backend_v2`  
3. Runs `docker compose up -d --build`  
4. Checks `http://VPS/gateway/health`

### C4. Change an env var (no Mac file)
GitHub → **Settings → Secrets** → edit e.g. `MYSQL_PASSWORD` or `GROQ_API_KEY`  
→ **Actions → Deploy → Run workflow** (or any small push to `main`).

---

## Part D — First successful deploy extras

### D1. Check API (HTTP)
```bash
curl -fsS http://145.223.21.127/gateway/health
curl -fsS http://145.223.21.127/api/v1/customer/settings
```

### D2. Enable HTTPS (once, on VPS Terminal)
```bash
cd /opt/sweetcrust/backend_v2
./deploy/hostinger/issue-cert.sh
```

Then:
```bash
curl -fsS https://api.bakerywala.cloud/gateway/health
```

### D3. Point apps at production
- Mobile: `EXPO_PUBLIC_API_URL=https://api.bakerywala.cloud`
- Admin: API base `https://api.bakerywala.cloud`

---

## Part E — Useful VPS commands

```bash
cd /opt/sweetcrust/backend_v2

# status
docker compose -f docker-compose.prod.yml --env-file .env.production ps

# logs
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f gateway nginx

# restart one service
docker compose -f docker-compose.prod.yml --env-file .env.production restart auth
```

---

## If deploy fails

| Failure | Fix |
|---------|-----|
| Smoke SSH / timeout | Firewall sync + SSH pubkey on VPS |
| Missing MYSQL_/JWT_/CERTBOT_ | Add those GitHub secrets |
| Missing `.env.production` | Secrets incomplete — check Actions log “Build .env.production” |
| Health check failed | On VPS: `docker compose … logs --tail=100` |
| Docker missing | First deploy runs `setup-vps.sh`; or install Docker in Terminal |

---

## Checklist (print this)

- [ ] Firewall 22/80/443 synced  
- [ ] SSH public key on VPS  
- [ ] GitHub secrets: HOSTINGER_* + MYSQL_* + JWT + CERTBOT_EMAIL  
- [ ] Workflow on `main`  
- [ ] `git push origin main` → Actions green  
- [ ] `curl http://145.223.21.127/gateway/health` OK  
- [ ] `issue-cert.sh` for HTTPS  
