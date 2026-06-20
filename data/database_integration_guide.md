# Database Integration Guide

## Overview
TechCorp Cloud's Sync API lets you connect an external database (PostgreSQL, MySQL, or MongoDB) to mirror data in near real time. This guide covers setup and common internal errors.

## Supported Connection Methods
1. **Direct connection** — TechCorp connects outbound to your database using credentials you provide. Requires your database to accept inbound connections from TechCorp's published IP range.
2. **Reverse tunnel agent** — a lightweight agent you run inside your network that establishes an outbound connection to TechCorp, avoiding the need to open inbound firewall rules. Recommended for databases behind a VPN or private subnet.

## Setting Up a Direct Connection
1. Go to Integrations → Databases → Add Connection.
2. Select your database type and enter host, port, database name, and credentials.
3. Allowlist TechCorp's IP range (published at status.techcorpcloud.com/ip-ranges) in your database firewall.
4. Click "Test Connection" before saving — this performs a read-only query to confirm connectivity without making any changes.

## Common Integration Errors

### "Connection Refused" / Internal Database Errors
Usually caused by one of:
- Firewall not allowlisting TechCorp's IP range (most common cause).
- Database max_connections limit reached — each TechCorp sync uses 2–5 concurrent connections depending on table volume.
- SSL/TLS mode mismatch — TechCorp requires `sslmode=require` or stricter for PostgreSQL; `verify-ca` and `verify-full` are also supported but require uploading your CA certificate.

### Sync Falls Behind / Internal Errors During Sync
- Large schema changes (adding/dropping columns) on the source table mid-sync can cause transient internal errors. The sync engine automatically retries and re-syncs the affected table; this can take several minutes for large tables.
- If errors persist beyond 30 minutes, check Integrations → Databases → [connection] → Logs for the specific failing table and error detail.
- Sustained internal errors not resolved by retry should be escalated with the connection ID and the table name from the logs — root-causing this typically requires engineering access to sync infrastructure.

### Schema Mismatch Errors
Occurs when the destination schema in TechCorp doesn't match the source after a structural change. Use "Re-sync Schema" under the connection settings to remap columns; this does not delete existing synced data.

## Performance Notes
Initial full sync throughput is roughly 5,000–10,000 rows/second depending on row size and network latency. Incremental syncs after the initial load typically complete within seconds of a source change, using change-data-capture (CDC) where supported (PostgreSQL, MySQL) or polling (MongoDB, every 30 seconds).

## Related Articles
- error_code_reference.md
- api_rate_limits.md
