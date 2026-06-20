# API Authentication Guide

## Overview
TechCorp Cloud's REST API uses Bearer token authentication. All requests must include a valid API key in the Authorization header.

## Generating an API Key
1. Go to Account Settings → API Keys.
2. Click "Generate New Key" and provide a label (e.g., "production-backend").
3. Copy the key immediately — it is shown only once and cannot be retrieved again. If lost, you must revoke it and generate a new one.
4. Keys are scoped to the workspace that created them and inherit that workspace's plan rate limits.

## Making Authenticated Requests
Include the key in the Authorization header using the Bearer scheme:

```
GET /v1/resources HTTP/1.1
Host: api.techcorpcloud.com
Authorization: Bearer tc_live_XXXXXXXXXXXXXXXXXXXX
Content-Type: application/json
```

## Common Authentication Errors

### 401 Unauthorized
Returned when:
- The Authorization header is missing entirely.
- The key is malformed (must start with `tc_live_` for production or `tc_test_` for sandbox).
- The key has been revoked or expired.
- The key was copied with leading/trailing whitespace or truncated during copy-paste.

Resolution: Verify the header is exactly `Authorization: Bearer <key>` with one space after "Bearer". Regenerate the key if you suspect it was copied incorrectly or has been revoked.

### 403 Forbidden
Returned when the key is valid but lacks permission for the requested resource (e.g., a read-only key attempting a write operation, or a sandbox key calling a production-only endpoint).

Resolution: Check the key's scope under Account Settings → API Keys → [key name] → Permissions. Generate a new key with the correct scope if needed.

### 429 Too Many Requests
Returned when the rate limit for your plan has been exceeded. See api_rate_limits.md for thresholds and the `Retry-After` header behavior.

## Key Rotation Best Practices
- Generate a new key before revoking the old one to avoid downtime.
- Run both keys in parallel for a short overlap window, then revoke the old key once traffic has fully shifted.
- Sandbox keys (`tc_test_`) never expire automatically; production keys (`tc_live_`) can optionally be set to auto-expire after 90/180/365 days under key settings.

## Related Articles
- api_rate_limits.md
- error_code_reference.md
- webhook_troubleshooting.md
