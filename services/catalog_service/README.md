# SweetCrust Catalog

Products, categories, geo

```bash
cd backend_v2
export PYTHONPATH="$PWD:$PWD/services/catalog_service"
./scripts/dev-service.sh catalog_service 8002
python -m app.check
```

## Layout

`app/{config,routes,controllers,services,repositories,producers,consumers,models,schemas}`
