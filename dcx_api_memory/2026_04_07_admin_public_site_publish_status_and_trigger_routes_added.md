The first manual public publish loop is now wired into `dcx_api`.

What was added:
- `admin/publish/public_site/read_dcx_admin_public_site_publish_status.py`
- `admin/publish/public_site/trigger_dcx_admin_public_site_publish_run.py`
- routes:
  - `/admin/publish/public-site/status`
  - `/admin/publish/public-site/run`

How it works:
- `status` upserts a default `dcx_public` state row if needed, reads the persisted publish metadata,
  and computes `pending_change_count` plus a short preview from current live public UX-string rows
  whose `updated_at_ts_ms` is newer than the last accepted publish timestamp.
- `run` requires the backend env var `DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL`, records a
  `deploy_requested` state, POSTs the Cloudflare Pages deploy hook, and if Cloudflare accepts the
  request it records `trigger_accepted` plus the accepted publish timestamp.

Important caveat:
- This MVP marks `last_successful_publish_at_ts_ms` at the moment Cloudflare accepts the deploy hook.
- It does not yet poll Cloudflare deployment completion or consume a callback webhook, so "accepted"
  means "Cloudflare accepted the rebuild request" rather than "the new site is definitely live".
- That tradeoff keeps the first loop simple while still making the admin status screen immediately useful.

Data dependency:
- The SQL table `stephen_dcx_public_content_publish_state` must exist before these routes work.
- The current routes follow the same temporary local `?admin_user_id=` gate as the other admin routes.
- Because production debug admin ids are still blocked, this publish screen is currently testable
  locally only until real auth is in place.

Verification completed:
- focused backend tests: 7 passed
