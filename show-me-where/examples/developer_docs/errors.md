# Errors

## Status codes

400 means the request was malformed. 401 means the key is missing or
revoked. 403 means the key is valid but not allowed for that resource. 404
means the resource does not exist. 429 means you hit the rate limit. 500
means something failed on our side; retry with backoff.

## Error bodies

Error responses carry a JSON body with a `code`, a human readable `message`
and a `request_id`. Send the `request_id` when you contact support.

## Idempotency

POST requests accept an Idempotency-Key header. Sending the same key twice
returns the same response instead of creating a second object. Keys can be
reused after 24 hours.
