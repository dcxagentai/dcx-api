CONTEXT:
This note records the backend hardening pass after the first app/email/WhatsApp multimedia plumbing
slice.

WHAT CHANGED:
- App-authored attachment messages now prepare attachment storage before creating the visible
  `stephen_dcx_contact_messages` row.
- The app path first confirms the authenticated user exists, uploads/validates the selected files
  into private R2, then opens the message transaction and persists the message, file-object rows,
  and attachment rows together.
- If final database persistence fails after R2 preparation, the backend attempts best-effort cleanup
  of the prepared R2 objects.
- Provider media attachment storage now checks for an existing attachment with the same
  `message_id` and `provider_media_id` before uploading another R2 object.
- The message schema SQL now declares a partial unique index on
  `stephen_dcx_contact_message_attachments (message_id, provider_media_id)` where
  `provider_media_id IS NOT NULL`.

WHY:
- Duplicate provider webhook delivery should not create duplicate attachment rows or duplicate R2
  objects for the same provider media item.
- App uploads should not leave a user-visible message row when an attachment is invalid, too large,
  unsupported, or cannot be stored.

FILES CHANGED:
- `messages/create_authenticated_dcx_app_contact_message.py`
- `messages/create_authenticated_dcx_app_contact_message_test.py`
- `messages/store_dcx_contact_message_attachment_file_object.py`
- `messages/store_dcx_contact_message_attachment_file_object_test.py`
- `storage/dcx_add_contact_messages_tables_2026_04_21.sql`

VERIFICATION:
- Focused backend tests:
  `.\\.venv\\Scripts\\python.exe -m pytest messages\\create_authenticated_dcx_app_contact_message_test.py messages\\store_dcx_contact_message_attachment_file_object_test.py messages\\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py messages\\process_dcx_resend_inbound_email_received_webhook_payload_test.py -q`
- Result: `13 passed in 0.43s`
- Broader message/file backend tests:
  `.\\.venv\\Scripts\\python.exe -m pytest dcx_api_app_test.py messages\\store_dcx_contact_message_attachment_file_object_test.py messages\\create_authenticated_dcx_app_contact_message_test.py messages\\read_authenticated_dcx_user_contact_message_detail_test.py messages\\read_authenticated_dcx_user_file_object_stream_by_file_uuid_test.py messages\\read_authenticated_dcx_user_contact_message_attachment_stream_test.py messages\\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py messages\\process_dcx_resend_inbound_email_received_webhook_payload_test.py -q`
- Result: `55 passed in 1.28s`

DEPLOYMENT NOTE:
- Live database should receive the new partial unique index before relying on the provider attachment
  invariant in production:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_contact_message_attachments_provider_media_uidx
ON stephen_dcx_contact_message_attachments (message_id, provider_media_id)
WHERE provider_media_id IS NOT NULL;
```

KNOWN LIMIT:
- The WhatsApp adapter may still download provider media bytes before the shared store discovers a
  duplicate attachment, because media download currently happens before canonical ingest. This pass
  prevents duplicate R2 objects and attachment rows, which is the important persistence invariant for
  the current smoke-test slice.
