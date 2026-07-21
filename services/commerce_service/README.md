# SweetCrust Commerce

Cart, orders, engagement

```bash
cd backend_v2
export PYTHONPATH="$PWD:$PWD/services/commerce_service"
./scripts/dev-service.sh commerce_service 8003
python -m app.check
```

## Layout

`app/{config,routes,controllers,services,repositories,producers,consumers,models,schemas}`
