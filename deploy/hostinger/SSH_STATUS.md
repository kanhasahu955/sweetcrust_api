# SSH / deploy status (Hostinger VPS)

| Item | Status |
|------|--------|
| VPS | `145.223.21.127` / id `1458436` — running |
| Account SSH key | Registered as **ashok-mac-github-ed25519** (id `537040`) |
| Attach via API | Hostinger returned incomplete attach; use panel → VPS → SSH keys if login fails |
| Port 22 from laptop | **Timed out** (2026-07-22) — open SSH in Hostinger firewall / browser console |

## Unblock SSH

1. Hostinger hPanel → VPS → **Browser terminal / Console** (as root).
2. Paste contents of `console-bootstrap.sh` (or run `setup-vps.sh` after uploading).
3. Panel → **SSH keys** → attach **ashok-mac-github-ed25519** (or add the pubkey to `/root/.ssh/authorized_keys`).
4. Confirm firewall allows TCP **22**, **80**, **443**.
5. From laptop:

```bash
cd backend_v2
cp .env.production.example .env.production   # fill secrets
./deploy/hostinger/check-ssh.sh
./deploy/hostinger/deploy.sh
./deploy/hostinger/issue-cert.sh             # after HTTP health OK
```

Public key on file:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINeFmwDt2d3+/3CwKxpWeihNJW8ngCQ7cQNyqOqyWvgX ashoksahu8018183830@gmail.com
```
