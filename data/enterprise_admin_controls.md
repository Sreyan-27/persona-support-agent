# Enterprise Admin Controls

## Overview
Enterprise-tier workspaces include an Admin Console that lets designated administrators manage security policy, billing, and member access across the organization.

## Accessing the Admin Console
Available at Account Settings → Organization (visible only to users with the Admin or Owner role). At least one Owner must exist per workspace at all times.

## Security Policies
Admins can configure:
- Mandatory 2FA enforcement for all members.
- Password expiration interval (default 180 days, configurable from 30–365 days).
- Single Sign-On (SSO) via SAML 2.0 (Okta, Azure AD, Google Workspace supported).
- IP allowlisting to restrict login access to specific corporate network ranges.
- Session timeout duration (default 12 hours of inactivity).

## Member Management
- Invite, suspend, or remove members from Organization → Members.
- Role types: Owner, Admin, Member, Read-Only Guest.
- Bulk invites are supported via CSV upload (max 500 rows per upload).
- Removing a member immediately revokes all active sessions and API keys tied to that user.

## Billing Visibility
Only Owners and Admins with the "Billing Manager" flag can view invoices, change the subscription plan, or update payment methods. This can be granted per-admin under Organization → Roles → Billing Access.

## SSO Setup Notes
SSO configuration changes can briefly lock out non-SSO sessions while DNS and certificate changes propagate (typically under 5 minutes). We recommend making SSO changes outside of peak business hours.

## Related Articles
- two_factor_authentication_setup.md
- subscription_plan_changes.md
- support_escalation_policy.txt
