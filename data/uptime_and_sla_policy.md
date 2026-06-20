# Uptime and SLA Policy

## Uptime Targets by Plan
| Plan | Uptime Target | SLA Credit Eligible |
|------|----------------|----------------------|
| Free | Best effort, no guarantee | No |
| Pro | 99.5% monthly | No |
| Business | 99.9% monthly | Yes |
| Enterprise | 99.95% monthly (custom terms available) | Yes |

## How Uptime Is Calculated
Uptime is measured as the percentage of each calendar month during which the core API (api.techcorpcloud.com) returned successful responses to automated health checks run every 60 seconds from 5 global regions. Scheduled maintenance windows (announced at least 72 hours in advance) are excluded from the calculation.

## Live Status Page
Real-time and historical uptime data is published at status.techcorpcloud.com, including incident postmortems for any outage exceeding 15 minutes.

## SLA Credits (Business and Enterprise only)
If monthly uptime falls below the plan's target:
| Uptime Achieved | Credit |
|------------------|--------|
| 99.0% – 99.9% (Business) | 10% of monthly fee |
| 95.0% – 99.0% | 25% of monthly fee |
| Below 95.0% | 50% of monthly fee |

Credits are applied to the following month's invoice automatically for Enterprise accounts with a named CSM; Business-tier customers must request the credit within 30 days of the affected billing period via a support ticket, since it requires manual verification against the incident log.

## Incident Communication
For incidents affecting Business/Enterprise customers, we provide:
- Initial notification within 15 minutes of detection.
- Status updates at least every 30 minutes during an active incident.
- A written postmortem within 5 business days for any incident causing more than 30 minutes of degraded service.

## Operational Impact Guidance for Account Teams
When discussing an active incident with an Enterprise customer, the current operational impact and estimated resolution time should always be sourced from the live status page or the assigned incident commander — never estimated ad hoc, as timelines change frequently during active incidents.

## Related Articles
- subscription_plan_changes.md
- support_escalation_policy.txt
