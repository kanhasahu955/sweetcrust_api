# Auth Service

OTP, JWT, Google, roles. Layout:

```
app/
  config/ controllers/ routes/ services/ repositories/
  producers/ consumers/ models/ schemas/
```

```bash
cd backend_v2
export PYTHONPATH="$PWD:$PWD/services/auth_service"
./scripts/dev-service.sh auth_service 8001
python -m app.check
```
