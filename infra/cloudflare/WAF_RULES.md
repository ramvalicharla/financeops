# Cloudflare WAF Rules for FinanceOps

## Active rules (verify in Cloudflare dashboard)

1. **Block common attack patterns**
   - SQL injection patterns
   - XSS patterns
   - Path traversal (../)

2. **Rate limiting rules**
   - /api/v1/auth/* - 10 requests/minute per IP
   - /api/v1/* - 100 requests/minute per IP
   - /api/v1/audit/portal/* - 30 requests/minute per IP

3. **Geo restrictions** (optional)
   - Consider allowing only IN, SG, AE, GB, US initially

4. **Bot protection**
   - Enable Bot Fight Mode
   - Challenge suspicious IPs

## Tunnel configuration
- Backend: http://backend:8000
- Frontend: http://frontend:3000
- Health check: /health (bypass WAF)
