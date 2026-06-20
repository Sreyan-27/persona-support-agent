# API Rate Limits

## Limits by Plan
| Plan | Requests / minute | Requests / month | Burst allowance |
|------|--------------------|--------------------|------------------|
| Free | 20 | 1,000 | 5 |
| Pro | 300 | 50,000 | 50 |
| Business | 1,200 | 250,000 | 200 |
| Enterprise | Custom (default 5,000) | Custom | Custom |

## How Rate Limiting Works
Limits are enforced per API key using a sliding-window algorithm over a 60-second period. Every response includes these headers so you can monitor usage proactively:

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 287
X-RateLimit-Reset: 1718812800
```

## Handling 429 Responses
When the limit is exceeded, the API returns HTTP 429 with a `Retry-After` header indicating the number of seconds to wait before retrying.

Recommended client-side handling:
1. Read the `Retry-After` header and wait that long before retrying.
2. Implement exponential backoff with jitter for repeated 429s, in case multiple clients are competing for the same key's quota.
3. Avoid generating a new request immediately on 429 — this can extend the throttling window for high-volume keys.

## Monthly Quota vs. Per-Minute Limit
These are independent. You can stay under the per-minute limit but still exhaust your monthly quota before the cycle resets. Monthly quota resets at 00:00 UTC on your billing anniversary date, not the calendar month start.

## Requesting a Temporary Limit Increase
Pro and Business customers can request a temporary 48-hour rate limit increase (e.g., for a product launch) via Account Settings → API Keys → Request Increase. Approval is automatic for increases up to 2x the plan default; larger increases require manual review (1 business day).

## Related Articles
- api_authentication_guide.md
- error_code_reference.md
