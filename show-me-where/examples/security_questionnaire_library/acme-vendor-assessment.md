# Acme vendor assessment

Quillix answers from a customer vendor assessment, March 2025.

## Data location

Primary customer data is stored in eu-west-1 (Dublin) and replicated to
eu-central-1 (Frankfurt). We do not store production customer data outside
those two regions.

## Encryption

All data in transit uses TLS 1.2 or newer. Data at rest is encrypted with
AES-256. Database snapshots are encrypted with the same standard.

## Breach notification

We notify affected customers within 72 hours of confirming a breach that
touches their data, by email to the security contact on the account.
