# Context

This note records a temporary debugging pass added to the first public waitlist intake route.

## What Changed

The backend route `POST /waitlist/email-signup` now logs:

- incoming request email
- incoming language code
- incoming signup page URL
- rejection error codes when validation fails
- normalized response values when validation succeeds

## Why

We wanted to inspect the exact request and response shape in the local backend terminal before moving on to the next persistence step.

## Follow-Up

Remove or narrow these raw request logs before production-style user data starts flowing through the route at scale.
