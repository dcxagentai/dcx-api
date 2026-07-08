# Content Page Translated Drafts Bulk Publish Added

The API now exposes an admin bulk publish action for content-page translations at `/admin/content/pages/publish-translated-drafts`. It accepts one `page_key`, locks current live non-original draft rows for that page, retires them, and inserts published successor rows while preserving immutable page version history.

The capability is idempotent for repeated admin use: when the page exists but no draft translations remain, it returns a no-op result. Missing translations are not created, and the public Astro rebuild remains a separate publish-site step.
