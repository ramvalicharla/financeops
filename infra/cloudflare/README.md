# Cloudflare WAF and Tunnel Configuration

## Current Target Domain
- API host: `api.finqor.ai`
- App host: `app.finqor.ai`

## WAF Rules
File: `waf_rules.json`

Apply manually in the Cloudflare Dashboard under Security -> WAF -> Custom Rules.

Target state in this repo:
- Managed rules: ON
- Auth rate limit: `api.finqor.ai/api/v1/auth/*` -> 10 req/min/IP
- API rate limit: `api.finqor.ai/api/*` -> 100 req/min/IP
- Block SQL injection (WAF score > 40)
- Block XSS (WAF score > 40)
- Block path traversal
- Managed challenge on `/admin`
- Block known bad bots
- Skip custom rules for `/health`

## Tunnel
File: `tunnel_config.yml`

Apply:
`cloudflared tunnel --config tunnel_config.yml run`

Exposes:
- `api.finqor.ai` -> `localhost:8000` (FastAPI)
- `app.finqor.ai` -> `localhost:3000` (Next.js)

## Terraform
- No Cloudflare Terraform file is currently present in this repo.
- This repo defines the desired state only; Cloudflare changes still need to be applied manually.
