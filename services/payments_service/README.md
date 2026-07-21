# SweetCrust Payments

Razorpay, COD, UPI

```bash
cd backend_v2
export PYTHONPATH="$PWD:$PWD/services/payments_service"
./scripts/dev-service.sh payments_service 8004
python -m app.check
```

## Layout

`app/{config,routes,controllers,services,repositories,producers,consumers,models,schemas}`
