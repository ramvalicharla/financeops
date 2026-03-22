# Uptime Monitoring Setup

## Endpoints to monitor

| Endpoint | Method | Expected Status | Alert if down > |
|---|---|---|---|
| /health | GET | 200 | 2 minutes |
| /api/v1/auth/login | POST | 200 or 422 | 5 minutes |
| /api/v1/erp-sync/connections | GET | 200 or 401 | 5 minutes |

## Recommended tool
UptimeRobot (free tier) or Better Uptime.

## Alert channels
Configure alerts to: email, Slack webhook (when available)

## Health check interpretation
- status=healthy -> all clear
- status=degraded -> investigate Celery workers, not urgent
- status=unhealthy -> page on-call immediately

