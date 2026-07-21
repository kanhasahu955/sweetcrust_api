# SweetCrust Delivery

Rider app + radius check

```bash
cd backend_v2
export PYTHONPATH="$PWD:$PWD/services/delivery_service"
./scripts/dev-service.sh delivery_service 8005
python -m app.check
```

## Layout

`app/{config,routes,controllers,services,repositories,producers,consumers,models,schemas}`
