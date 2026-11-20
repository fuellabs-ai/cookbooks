# Rate limits

## Plan limits

The free plan allows 60 requests per minute and the pro plan allows 600
requests per minute. Both plans allow a burst of 2x for up to 10 seconds.

## When you hit the limit

Requests over the limit get a 429 response with a Retry-After header that
says how many seconds to wait. Retry with exponential backoff rather than a
fixed loop.

## Rate limit headers

Every response includes X-RateLimit-Limit, X-RateLimit-Remaining and
X-RateLimit-Reset so you can pace requests without guessing.
