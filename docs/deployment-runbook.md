# FinanceOps Deployment Runbook

## Running Migrations (Railway Only)

Database migrations are **not** executed by FastAPI startup.

Run migrations only inside the deployment environment (Railway) where
production networking and secrets are available.

Do **not** run production migrations from a developer local machine.
Local DNS/network access to Supabase or private infrastructure can fail and
is not part of the production migration path.

### Railway migration command
```bash
cd backend
alembic upgrade head
```

### Railway helper script
```bash
bash scripts/run_migrations.sh
```

## Pre-deployment checklist

- [ ] All tests passing locally (pytest tests/ -x -q)
- [ ] Playwright tests passing (npx playwright test)
- [ ] Frontend build clean (npm run build)
- [ ] Alembic chain clean (alembic check)
- [ ] .env.production values set and reviewed
- [ ] FIELD_ENCRYPTION_KEY backed up securely
- [ ] Database backup taken before migration

## Deployment steps

### 1. Pull latest code
```bash
git pull origin main
git checkout v1.x.x  # specific version tag
```

### 2. Run database migrations
```bash
cd backend
alembic upgrade head
```

### 3. Deploy services
```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --build
```

### 4. Verify health
```bash
curl https://api.financeops.in/health
curl https://app.financeops.in
docker compose -f docker-compose.prod.yml ps
```

### 5. Smoke test
- Login works
- MIS page loads
- Search works (Cmd+K)
- Notifications bell works

## Rollback procedure

If deployment fails:
```bash
# Roll back to previous version
git checkout v1.x.x-previous
docker compose -f docker-compose.prod.yml up -d --build

# Roll back database (if migration was applied)
alembic downgrade -1
```

## Emergency contacts
- On-call: [your contact]
- Cloudflare dashboard: https://dash.cloudflare.com
- Database: check pg_stat_activity for blocking queries

## Common issues

**Backend won't start:**
Check FIELD_ENCRYPTION_KEY is set and is valid base64.
Check DATABASE_URL is reachable from container.

**Migrations fail:**
Check alembic heads - should be single head.
Check database user has DDL permissions.

**Redis connection refused:**
Check REDIS_PASSWORD matches in both backend and redis service.
