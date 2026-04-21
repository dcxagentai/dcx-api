# 2026-04-21 Newsletter Audience Scope And Sequence Schedule First Pass

## What changed
- Added newsletter prepare-time audience scoping with `send_audience_scope` values `all`, `admins`, and `devs`.
- Kept the existing DB-safe `send_audience_type='newsletters'` value and stored the real scope in `send_summary_json`.
- Updated the newsletter sends catalog to expose `send_audience_scope` back to the admin frontend.
- Added first-pass sequence backend capabilities:
  - create draft
  - read catalog
  - read detail
  - save sequence metadata and replace the full ordered step list
- Added first-pass schedule backend capability that aggregates:
  - scheduled newsletter send rows
  - scheduled sequence-launch rows

## Why this shape
- The live schema enum for `send_audience_type` does not currently include `admins` or `devs`, so the safest path was to keep the DB enum-compatible value and carry the real demo/operator scope separately.
- For sequences, the first useful demo stage is a coherent planning/editor model, not dispatch. One save capability that replaces the full step list is simpler and less brittle than multiple partial step mutations.
- The schedule route is intentionally narrow: it proves we can aggregate timed work across domains without pretending content-page scheduling already exists.

## Verification
- Targeted backend pytest slice passed:
  - newsletter audience prepare test
  - newsletter sends catalog test
  - sequence create/catalog/detail/save tests
  - schedule catalog test
- Result: `17 passed`

## Remaining follow-up
- Sequence dispatch/recipient preparation is not implemented yet.
- The schedule route does not yet include content-page publish windows because that scheduling model does not exist in the backend yet.
- If we later want `admins` / `devs` as first-class send audience enums in the DB, we should widen the schema deliberately rather than keep only the JSON summary field.
