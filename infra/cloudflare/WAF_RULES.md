# Cloudflare WAF Rules for Finqor

## Target state (verify in Cloudflare dashboard)

1. **Managed protection**
   - Managed rules: ON
   - Bot protection: ON

2. **Rate limiting rules**
   - `api.finqor.ai/api/v1/auth/*` - 10 requests/minute per IP
   - `api.finqor.ai/api/*` - 100 requests/minute per IP

3. **Custom attack blocking**
   - SQL injection patterns
   - XSS patterns
   - Path traversal (`../`)

4. **Route handling**
   - Managed challenge on `/admin`
   - Skip custom rules for `/health`

## Tunnel configuration
- Backend: `api.finqor.ai` -> `http://localhost:8000`
- Frontend: `app.finqor.ai` -> `http://localhost:3000`
- Health check: `/health`
