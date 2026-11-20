# Webhooks

## Registering an endpoint

Add an HTTPS endpoint in the dashboard under Developers then Webhooks. We
POST a JSON event for each change you subscribe to.

## Verifying signatures

Every delivery carries an X-Tidegate-Signature header with an HMAC of the
raw body using your endpoint signing secret. Verify it before trusting the
payload.

## Retries

A delivery that does not get a 2xx response is retried 5 times over 24
hours with increasing gaps. You can redeliver any event manually from the
dashboard event log.
