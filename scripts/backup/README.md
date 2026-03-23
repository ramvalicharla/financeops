# FinanceOps Backup and DR Runbook
## RTO and RPO
RTO (Recovery Time Objective): 4 hours
RPO (Recovery Point Objective): 1 hour

## Backup Schedule
Full backup:        Daily at 02:00 UTC
Incremental (WAL):  Every 1 hour
Redis backup:       Every 6 hours

## Restore Procedure
1. Stop all API workers
2. Run: RESTORE_CONFIRM=yes ./restore_postgres.sh <filename>
3. Run: ./verify_restore.sh
4. Run: alembic upgrade head (if needed)
5. Restart workers
6. Monitor /health for 30 minutes

## Retention
Full backups: 30 days | WAL: 7 days | Redis: 7 days
