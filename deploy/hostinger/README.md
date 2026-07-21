# Hostinger VPS — production deploy (`backend_v2`)

| | |
|--|--|
| VPS | `145.223.21.127` (Ubuntu 22.04, KVM 2) |
| API | `https://api.bakerywala.cloud` |
| Path on server | `/opt/sweetcrust/backend_v2` |

DNS: `api.bakerywala.cloud` A → `145.223.21.127` (already configured).

## GitHub Actions CI/CD

**backend_v2 only** — push this folder as its own GitHub repo. See [`GITHUB_ACTIONS.md`](GITHUB_ACTIONS.md) and [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml).

## One-time on the VPS

1. Attach SSH key **ashok-mac-github-ed25519** (already registered on the Hostinger account; id `537040`) in hPanel → VPS → SSH keys. See [`SSH_STATUS.md`](SSH_STATUS.md) if port 22 times out.
2. SSH in and install Docker:

```bash
ssh root@145.223.21.127
# paste setup-vps.sh or:
curl -fsSL https://raw.githubusercontent.com/…   # or scp the script
bash /opt/sweetcrust/backend_v2/deploy/hostinger/setup-vps.sh
```

## First deploy from your laptop

```bash
cd backend_v2
cp .env.production.example .env.production
# Edit: MYSQL_* passwords, JWT_SECRET_KEY, CERTBOT_EMAIL, Razorpay/Groq keys, CORS_ORIGINS
# Remove all CHANGE_ME values.

export DEPLOY_HOST=145.223.21.127 DEPLOY_USER=root
./deploy/hostinger/deploy.sh
```

Then TLS:

```bash
ssh root@145.223.21.127 'cd /opt/sweetcrust/backend_v2 && ./deploy/hostinger/issue-cert.sh'
```

## Smoke tests

```bash
curl -fsS http://145.223.21.127/gateway/health
curl -fsS https://api.bakerywala.cloud/gateway/health
curl -fsS https://api.bakerywala.cloud/api/v1/customer/settings
```

## Day-2 ops (on server)

```bash
cd /opt/sweetcrust/backend_v2
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f gateway nginx
docker compose -f docker-compose.prod.yml --env-file .env.production restart auth
```

Renew certs (cron monthly is fine):

```bash
./deploy/hostinger/issue-cert.sh
# or: docker compose -f docker-compose.prod.yml --env-file .env.production --profile certbot run --rm certbot renew
# then reload nginx
```

## Rollback

```bash
# Keep previous image tags / re-rsync an older commit, then:
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

MySQL data lives in the `mysql_data` Docker volume — `down` without `-v` keeps the DB.

## Point apps at production

- Customer / retailer mobile: `EXPO_PUBLIC_API_URL=https://api.bakerywala.cloud`, socket same host (`/socket.io`)
- Admin Nuxt: API base → `https://api.bakerywala.cloud`

## Memory note

~30 containers on 8GB is tight. Soft limits are in `docker-compose.prod.yml`. If the host OOMs, upgrade the VPS or temporarily stop `ai` / `forecast`.
