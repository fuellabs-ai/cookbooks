# SDK install

## Python

Install with `pip install tidegate`. The SDK supports Python 3.9 and newer.
Set your key with `tidegate.api_key = "sk_test_..."` before your first call.

## Node

Install with `npm install @tidegate/node`. The SDK supports Node 18 and
newer.

## Timeouts

Requests time out after 30 seconds by default. Pass a `timeout` option, in
seconds, when you need longer for a slow endpoint.

## Versioning

The SDKs follow the API version calendar. Pin the SDK version in your lock
file; minor releases never change existing responses.
