# `backend_v2/package` — shared FastAPI infra

**Tooling:** install deps from `backend_v2/` with `uv sync` (optional `uv sync --extra ai`). Run checks with `uv run`.

**Credentials:** every service + this package reads `backend_v2/.env` via `package.common.env` (`ROOT_ENV`). Independent of legacy `backend/`.

```
package/
├── common/
│   ├── env.py           # ROOT_ENV (backend_v2/.env) + service_env_files()
│   ├── settings.py      # shared Settings + configure_settings()
│   ├── errors.py        # AppError + DB/HTTP/validation handlers
│   ├── schemas.py       # API envelopes (ok/fail/HealthOut)
│   ├── middleware.py    # CORS + request-id/timing + errors
│   ├── lifecycle.py     # lifespan: log → DB → boot banner → disconnect
│   ├── factory.py       # create_service_app (wires middleware + errors)
│   ├── auth/            # JWT + guards (claims only)
│   └── utils/           # utc_now, slugify, passwords, …
├── database/            # connect/disconnect/sessions/pool/replica
├── redis/               # cache + locks (realtime fan-out)
├── logger/              # colorized logs + startup report
├── dto/                 # re-exports common.schemas
├── events/              # topic names
└── metrics/             # stub
```

Domain `models/` + `schemas/` stay **inside each service**.
Infra (logging, middleware, errors, datetime, DB, redis) always comes from `package/`.

## Quick use (every FastAPI service)

```python
from package.common.settings import configure_settings, get_settings, Settings
from package.common.factory import create_service_app          # → setup_middleware + errors
from package.common.lifecycle import service_lifespan         # → setup_logging + boot banner
from package.common.errors import NotFoundError, ForbiddenError, BadRequestError, ConflictError
from package.common.schemas import APIModel, HealthOut, ok, fail
from package.common.utils import utc_now, utc_today, day_bounds  # never datetime.utcnow()
from package.common.auth import AccessToken, load_user, require_roles
from package.common.rate_limit import enforce_rate
from package.database import SessionDep, session_scope, ping_db, pool_status
from package.logger import get_logger
from package.redis import redis_ping, redis_publish
from package.events.topics import CHAT_MESSAGE, ORDER_STATUS, DELIVERY_LOCATION

logger = get_logger(__name__)
# raise NotFoundError(...) — middleware turns AppError into JSON envelopes
# Field(default_factory=utc_now) on model timestamps
```

```bash
export PYTHONPATH=backend_v2
python -m package.check_package
```

## Env knobs (shared)

| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | Primary MySQL |
| `DATABASE_READ_URL` | Optional replica / LB read VIP |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_RECYCLE` | Pool |
| `DB_LOG_SLOW_MS` | Slow-query log threshold |
| `REDIS_URL` | Realtime / cache |
| `LOG_LEVEL` / `LOG_JSON` / `LOG_COLOR` | Logger |
| `REQUEST_LOG` | Per-request access lines |
| `SERVICE_NAME` / `SERVICE_VERSION` | Boot banner identity |
