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

## Part B — One-time GitHub setup

### B1. Open secrets
https://github.com/kanhasahu955/sweetcrust_api/settings/secrets/actions  
→ **New repository secret** for each:

| Secret name | Value |
|-------------|--------|
| `HOSTINGER_HOST` | `145.223.21.127` |
| `HOSTINGER_USER` | `root` |
| `HOSTINGER_SSH_KEY` | Full **private** key (`cat ~/.ssh/hostinger_gha` — BEGIN…END) |
| `MYSQL_ROOT_PASSWORD` | strong password |
| `MYSQL_PASSWORD` | strong password |
| `JWT_SECRET_KEY` | long random string |
| `CERTBOT_EMAIL` | your email |

Optional later: `GROQ_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, etc.

### B2. Confirm workflow exists
File in repo: `.github/workflows/deploy.yml`  
Trigger: **push to `main`** (and manual Run workflow).

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
