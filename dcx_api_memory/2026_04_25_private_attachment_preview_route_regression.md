# 2026-04-25 Private Attachment Preview Route Regression

## Context

During the first Gemini message-analysis pass, the app Messages preview pane temporarily lost working media previews and Open links for existing attachments. Message metadata and Gemini analysis fields loaded correctly, but image previews, audio playback, and Open links failed or hung.

This was confusing because the basic file plumbing had already been smoke tested successfully across app, WhatsApp, and email surfaces.

## What Broke

The message detail payload had been changed to prefer the newer flat private file URL:

```text
/users/me/files/{file_uuid}
```

That route is conceptually useful because it hides message ids, attachment ids, database ids, and R2 keys. But during this MVP pass, it introduced unnecessary moving parts into the display path while the older message attachment route was already working:

```text
/users/me/messages/{message_id}/attachments/{attachment_id}/file
```

We also briefly added `Cross-Origin-Resource-Policy: same-site` to private media responses. That header is not needed for this current app delivery path and can interfere with localhost/dev-origin media display.

## Working Solution

For now, message detail attachment URLs always use the known-working attachment route:

```text
/users/me/messages/{message_id}/attachments/{attachment_id}/file
```

This restores the boring, explicit flow:

1. Message detail returns an attachment route URL.
2. The route authenticates the app session.
3. The route looks up the attachment row by `message_id` and `attachment_id`.
4. The capability joins to `stephen_dcx_file_objects`.
5. The backend reads the R2 object using `bucket_alias` and `object_key`.
6. The backend returns bytes with the stored content type.
7. The frontend uses that URL directly in `img`, `audio`, and Open links.

## Files Touched

- `messages/read_authenticated_dcx_user_contact_message_detail.py`
  - Restored attachment URLs to `/users/me/messages/{message_id}/attachments/{attachment_id}/file`.
- `routes/users/dcx_api_routes_users_me_message_attachment_file.py`
  - Serves private attachment bytes without `Cross-Origin-Resource-Policy`.
- `routes/users/dcx_api_routes_users_me_file_object.py`
  - Keeps the flat file UUID route available, with byte-range support, but this is no longer the default URL emitted by message detail.
  - Also no longer sends `Cross-Origin-Resource-Policy`.
- `dcx_api_app_test.py`
  - Updated private media route expectations so the resource-policy header is absent.
- `messages/read_authenticated_dcx_user_contact_message_detail_test.py`
  - Updated expected attachment URL shape.
- `dcx_app/src/components/dcx_app_messages_page.tsx`
  - Confirmed frontend is back to direct URL rendering for image/audio/Open links.

## Verification

Focused backend tests:

```text
45 passed
```

Frontend build:

```text
npm run build
```

Result:

```text
build passed
```

Only the existing Vite large chunk warning remains.

Manual smoke check from the app surface confirmed:

- image preview displays
- audio preview plays with correct duration
- attachment Open links are available again

## Decision

Keep the route boring for MVP.

Use the attachment route as the canonical message-detail preview/download URL until there is a stronger reason to expose flat file UUID URLs by default. The flat `/users/me/files/{file_uuid}` route can remain as a future-friendly endpoint, but it should not be used in the user-facing attachment preview path until separately smoke tested across the same browser/app deployment contexts.

## What Comes Next

- If we later need flat file URLs, test them independently with:
  - image preview
  - audio playback with duration/range requests
  - document Open
  - localhost app to local API
  - dev app to dev API
  - production app to production API
- Consider signed short-lived file URLs later, especially if file sharing or non-session delivery becomes necessary.
- Keep direct attachment route behavior as the stable MVP baseline.
