# Webhook Troubleshooting

## Overview
Webhooks notify your application in real time when events occur (e.g., `subscription.updated`, `payment.failed`, `user.created`). This guide covers configuration and common delivery failures.

## Setting Up a Webhook
1. Go to Account Settings → Webhooks → Add Endpoint.
2. Enter a publicly reachable HTTPS URL (HTTP-only and localhost URLs are rejected).
3. Select the event types to subscribe to.
4. Copy the signing secret shown — you'll need it to verify payload authenticity.

## Verifying Webhook Signatures
Every webhook request includes a `X-TechCorp-Signature` header, an HMAC-SHA256 hash of the raw request body using your endpoint's signing secret. Always verify this signature before processing a payload to prevent spoofed requests. Reject any request where the computed signature doesn't match.

## Common Delivery Failures

### Endpoint Returns Non-2xx Status
We treat any non-2xx response as a failure and retry. Common causes: endpoint throwing a 500 due to unhandled exceptions, or returning 401/403 because the receiving server expects its own auth header in addition to the signature.

### Endpoint Times Out
We wait 10 seconds for a response. If your handler does slow processing (e.g., database writes, third-party API calls) before responding, move that work to a background job and return a 200 immediately upon receipt.

### Retry Schedule
Failed deliveries are retried with exponential backoff: 1 min, 5 min, 30 min, 2 hr, 6 hr, then once daily for up to 3 days. After 3 days of consecutive failures, the endpoint is automatically disabled and an alert email is sent to the workspace owner.

### Duplicate Events
Because of retries, your endpoint may occasionally receive the same event twice. Each payload includes a unique `event_id` — store processed IDs and ignore duplicates to keep your handler idempotent.

## Testing Webhooks
Use the "Send Test Event" button on the webhook detail page to fire a sample payload of any event type to your endpoint without waiting for a real trigger. The Webhook Logs tab shows the last 200 delivery attempts with status codes and response bodies for debugging.

## Related Articles
- api_authentication_guide.md
- error_code_reference.md
