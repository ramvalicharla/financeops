# Deployment Runbook

## Payment Configuration

Set these environment variables from the Razorpay dashboard before deployment:

- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`

Webhook signature verification is enforced for incoming Razorpay webhook events.

### Staging Go-Live Validation

1. Create a test order in staging.
2. Complete payment using a Razorpay test card.
3. Verify the credit ledger is updated.
4. Verify webhook delivery was received and processed successfully.
