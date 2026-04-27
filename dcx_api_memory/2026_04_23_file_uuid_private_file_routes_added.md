CONTEXT:
This note records the shift from nested message attachment URLs to flat file UUID URLs for private
DCX app file reads.

WHAT CHANGED:
- `stephen_dcx_file_objects` gained a nullable unique `file_uuid` column via manual SQL.
- New file-object inserts now generate `file_uuid` in Python, matching the existing user UUID
  strategy rather than relying on a database UUID default.
- Message detail attachment payloads now prefer `/users/me/files/{file_uuid}` when `file_uuid`
  exists.
- The old `/users/me/messages/{message_id}/attachments/{attachment_id}/file` route remains as a
  compatibility path for older rows where `file_uuid` is still null.
- A new authenticated file route streams private files by file UUID after checking the current user
  owns the file object.

WHY:
- App-visible file URLs should not expose message ids, attachment ids, database primary keys, or R2
  object keys.
- R2 object keys remain fully flat and opaque storage addresses.
- Postgres remains the source of truth for ownership, file metadata, message links, and access
  control.

VERIFICATION:
- Ran focused backend tests:
  `.\\.venv\\Scripts\\python.exe -m pytest dcx_api_app_test.py messages\\store_dcx_contact_message_attachment_file_object_test.py messages\\read_authenticated_dcx_user_contact_message_detail_test.py messages\\read_authenticated_dcx_user_file_object_stream_by_file_uuid_test.py messages\\read_authenticated_dcx_user_contact_message_attachment_stream_test.py -q`
- Result:
  `46 passed in 1.36s`
- Ran app build:
  `npm run build`
- Result:
  Build passed with the existing large chunk warning.

WHAT COMES NEXT:
- Apply the same `file_uuid` schema addition on live before deploying code that inserts
  `file_uuid`.
- Backfill existing file rows with app-generated UUIDs or a controlled SQL/Python utility before
  enforcing `file_uuid NOT NULL`.
