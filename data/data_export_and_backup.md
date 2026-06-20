# Data Export and Backup

## Self-Service Export
All plans can export their workspace data at any time from Account Settings → Data → Export.
- Format: CSV for tabular data, JSON for full structured export including metadata.
- Large workspaces (over 1 GB) are packaged as a zip and emailed as a download link valid for 7 days, rather than downloaded directly in-browser.
- Exports include all records the requesting user has read access to; workspace-wide exports require Admin or Owner role.

## Automatic Backups
TechCorp Cloud performs automatic backups of all workspace data:
- Snapshot frequency: every 6 hours.
- Retention: 30 days for Pro/Business, 90 days for Enterprise.
- Backups are stored encrypted at rest in a separate geographic region from primary storage.

## Restoring from Backup
Self-service restore is not available, since restoring can overwrite current data and is irreversible. To request a restore:
1. Identify the approximate date/time the data needs to be restored to.
2. Contact support with the workspace ID and target restore point.
3. A human engineer performs the restore to a temporary workspace first, so you can verify the data before it's merged into production. This typically takes 1–2 business days for Pro/Business, and within 4 hours for Enterprise (per SLA).

## Account Deletion and Data Retention
When a workspace is deleted (by the Owner, via Account Settings → Danger Zone), data enters a 30-day soft-delete period during which it can be restored on request. After 30 days, data is permanently purged and cannot be recovered, including from backups.

## Related Articles
- enterprise_admin_controls.md
- uptime_and_sla_policy.md
