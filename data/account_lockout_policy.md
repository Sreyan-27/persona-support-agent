# Account Lockout Policy

## Trigger Conditions
An account is automatically locked when any of the following occur:
- 5 consecutive failed password attempts within a 10-minute window.
- 3 failed 2FA code attempts within a 5-minute window.
- Repeated login attempts from more than 4 distinct geographic regions within 1 hour (flagged as suspicious activity).

## Standard Lockout (Failed Password/2FA Attempts)
- Duration: 15 minutes, after which the account automatically unlocks.
- A successful password reset immediately clears the lockout regardless of the timer.
- The user receives an email notification when a lockout is triggered, including the approximate location and device of the attempt.

## Security Lockout (Suspicious Activity)
- Duration: Indefinite, pending manual review.
- These lockouts cannot be cleared via self-service password reset.
- The Account Security team must verify the user's identity via a secondary channel (phone or verified recovery email) before lifting the lock.
- Typical resolution time: 4–24 business hours.

## Repeated Lockouts
If a user is locked out more than 3 times within a 7-day period, the account is automatically flagged for a manual security review even if each individual incident was a standard lockout. This is a precaution against credential-stuffing attacks.

## What Support Agents Can Do
- Standard lockouts: confirm identity via account email and registered phone number, then manually clear the lockout timer if the user cannot wait the full 15 minutes.
- Security lockouts: cannot be cleared by tier-1 support. Must be escalated to Account Security.

## Related Articles
- password_reset_guide.pdf
- two_factor_authentication_setup.md
