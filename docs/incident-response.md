# Incident Response Guide

## Severity levels

| Level | Description | Response time | Example |
|-------|-------------|---------------|---------|
| P1 | Platform down | 30 minutes | All users cannot login |
| P2 | Core feature broken | 2 hours | MIS reports not loading |
| P3 | Feature degraded | 8 hours | Export failing |
| P4 | Minor issue | 48 hours | UI cosmetic bug |

## P1 Response procedure

1. **Detect** - Grafana alert fires or customer reports
2. **Acknowledge** - One person owns the incident
3. **Diagnose**
```bash
   docker compose logs backend --tail=100
   docker compose logs db --tail=50
   curl https://api.financeops.in/health
```
4. **Communicate** - Update status page within 15 minutes
5. **Mitigate** - Rollback if needed (see deployment runbook)
6. **Resolve** - Fix root cause
7. **Post-mortem** - Write up within 48 hours

## Data breach procedure

Per DPDP Act 2023:
1. Contain breach immediately
2. Notify Data Protection Officer within 6 hours
3. Assess scope - which tenants affected?
4. Notify affected tenants within 72 hours
5. Notify Data Protection Board if required
6. Document everything

## Useful commands
```bash
# Check active DB connections
docker compose exec db psql -U financeops -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Check Redis memory
docker compose exec redis redis-cli -a $REDIS_PASSWORD info memory

# Check Celery queue depth
docker compose exec backend celery -A financeops.tasks.celery_app \
  inspect active_queues

# Tail backend logs
docker compose -f docker-compose.prod.yml logs -f backend
```
