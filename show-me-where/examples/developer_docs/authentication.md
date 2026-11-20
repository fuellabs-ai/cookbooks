# Authentication

## API keys

Every request needs an API key from the dashboard under Settings then API
keys. Send it in the Authorization header as a Bearer token.

## Key prefixes

Sandbox keys start with sk_test_ and live keys start with sk_live_. Sandbox
keys never touch production data and have separate rate limits.

## Rotating a key

Create the new key first, switch your traffic over, then revoke the old key
from the dashboard. Both keys work at the same time during the switch.

## Keeping keys safe

Keys give full account access, so never put them in client-side code, public
repositories or support tickets. If a key leaks, revoke it immediately.
