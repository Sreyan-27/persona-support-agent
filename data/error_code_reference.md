# API Error Code Reference

## HTTP Status Codes

| Code | Meaning | Common Cause | Resolution |
|------|---------|--------------|------------|
| 400 | Bad Request | Malformed JSON body, missing required field | Validate request body against the API schema docs |
| 401 | Unauthorized | Missing/invalid/expired API key | See api_authentication_guide.md |
| 403 | Forbidden | Key lacks permission for this resource | Check key scope/permissions |
| 404 | Not Found | Resource ID doesn't exist or belongs to another workspace | Verify the resource ID and workspace context |
| 409 | Conflict | Duplicate resource creation (e.g., idempotency key reuse with different payload) | Use a unique idempotency key per distinct request |
| 422 | Unprocessable Entity | Request is well-formed but fails business validation | Check the `errors` array in the response body for field-level detail |
| 429 | Too Many Requests | Rate limit exceeded | See api_rate_limits.md |
| 500 | Internal Server Error | Unexpected server-side failure | Retry with backoff; if persistent, escalate with the `request_id` from response headers |
| 503 | Service Unavailable | Planned maintenance or transient overload | Check status.techcorpcloud.com; retry after the indicated window |

## Application-Level Error Codes
Beyond HTTP status, error responses include a JSON body with a specific `error_code` field for finer-grained diagnosis:

```json
{
  "error_code": "INVALID_API_KEY_FORMAT",
  "message": "The provided API key does not match the expected format.",
  "request_id": "req_8f3a1b2c"
}
```

Common `error_code` values:
- `INVALID_API_KEY_FORMAT` — key doesn't start with `tc_live_` or `tc_test_`
- `KEY_REVOKED` — key was manually revoked in the dashboard
- `RESOURCE_LOCKED` — resource is mid-migration and temporarily read-only
- `SCHEMA_VALIDATION_FAILED` — request body failed schema checks (see `errors` array for field paths)
- `IDEMPOTENCY_KEY_CONFLICT` — same idempotency key reused with a different request payload

## Including request_id in Support Requests
Every API response includes a unique `request_id`. Always include this when reporting an issue — it lets support and engineering trace the exact request through internal logs without needing to reproduce the issue.

## Related Articles
- api_authentication_guide.md
- api_rate_limits.md
- database_integration_guide.md
