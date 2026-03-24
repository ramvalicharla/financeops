# Cloudflare WAF and Tunnel Configuration

## WAF Rules
File: `waf_rules.json`

Apply via Cloudflare Dashboard -> Security -> WAF -> Custom Rules

Or via Terraform:
`terraform apply infra/terraform/cloudflare.tf`

Rules summary:
- Rate limit: 1,000 req/min on `/api/v1/*`
- Block SQL injection (WAF score > 40)
- Block XSS (WAF score > 40)
- Block path traversal
- Managed challenge on `/admin` routes
- Block known bad bots
- Skip rules for `/health` endpoint

## Tunnel
File: `tunnel_config.yml`

Apply:
`cloudflared tunnel --config tunnel_config.yml run`

Exposes:
- `api.financeops.app` -> `localhost:8000` (FastAPI)
- `app.financeops.app` -> `localhost:3000` (Next.js)

## Updating Rules
1. Edit `waf_rules.json`
2. Commit to `main`
3. CI applies via Cloudflare API (requires `CF_API_TOKEN` secret)

