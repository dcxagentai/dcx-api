The first public publish loop now distinguishes local and hosted behavior cleanly.

What changed:
- `trigger_dcx_admin_public_site_publish_run_capability` now branches by `DCX_ENVIRONMENT`.
- In `local` / `development`:
  - `Publish public site` no longer calls the Cloudflare Pages deploy hook.
  - It records `last_publish_status = local_manual_rebuild_required`.
  - It stores a message telling the developer to run `npm run dev` or `npm run build` in `dcx_public`.
- In hosted environments:
  - The existing Cloudflare Pages deploy-hook behavior remains unchanged.

Additional route/capability added:
- `admin/publish/public_site/mark_dcx_admin_public_site_local_rebuild_complete.py`
- route:
  - `/admin/publish/public-site/mark-local-rebuild-complete`

Purpose:
- After the developer manually refreshes or rebuilds `dcx_public` locally, the admin UI can mark
  that local rebuild complete and reset the pending-change baseline.

Verification completed:
- focused backend tests: 11 passed
