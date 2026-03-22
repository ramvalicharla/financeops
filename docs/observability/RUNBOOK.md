# FinanceOps Runbook

## Incident: Database unreachable
1. Check finos-postgres container: `docker ps | grep postgres`
2. Check connection pool: `GET /health` -> `database.status`
3. Restart: `docker restart finos-postgres`
4. Verify: `GET /health`

## Incident: Redis unreachable
1. Check finos-redis container: `docker ps | grep redis`
2. Check: `GET /health` -> `redis.status`
3. Restart: `docker restart finos-redis`
4. Note: idempotency keys lost on Redis restart - duplicate requests possible for 24h

## Incident: Celery queue depth > 100
1. Check: `GET /health` -> `queues`
2. Check worker logs: `docker logs finos-worker --tail 100`
3. Scale workers: `docker compose up --scale finos-worker=3`

## Incident: Sync run stuck in RUNNING > 30 minutes
1. Check worker logs for the sync run ID
2. Check Redis for stuck idempotency keys
3. Manually set run status to HALTED via admin endpoint

## Incident: Payment webhook not processing
1. Check WebhookEvent table for `processing_error`
2. Check Sentry for task failure
3. Retry: `POST /billing/admin/retry-webhook/{id}`

## Incident: ClamAV unavailable
1. Check container: `docker ps | grep clamav`
2. Check logs: `docker logs finos-clamav --tail 50`
3. Note: if `CLAMAV_REQUIRED=true`, file uploads will be rejected until ClamAV recovers
4. Restart: `docker restart finos-clamav`
5. ClamAV takes ~2 minutes to reload virus signatures after restart
