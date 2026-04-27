CONTEXT:
This note records the app-surface file upload fix after smoke tests showed text messages worked but
 app-authored image/audio/document attachments never reached R2.

WHAT HAPPENED:
- The app frontend file picker and `FormData` submission were already correct.
- The failure happened at the authenticated app route boundary:
  `routes/users/dcx_api_routes_users_me_messages_create.py`
- The route manually parsed `request.form()` and filtered each `message_files` item with
  `isinstance(uploaded_file, fastapi.UploadFile)`.
- In practice `request.form()` returned `starlette.datastructures.UploadFile`, so valid uploaded
  files were skipped and the message capability received `attachment_inputs=[]`.
- That made the app surface create text-only messages while never invoking the shared attachment
  storage path or R2 upload.

WHAT CHANGED:
- Rewired the route boundary to the proper FastAPI multipart contract:
  - `message_text: str = Form("")`
  - `message_files: list[UploadFile] | None = File(None)`
- The route now converts those uploaded files directly into the existing canonical
  `attachment_inputs` structure and passes them into
  `create_authenticated_dcx_app_contact_message`.
- The route now also translates shared attachment capability errors more directly:
  - too large
  - unsupported / invalid
  - storage failed

WHY THIS IS THE RIGHT SHAPE:
- It keeps the existing downstream app/email/WhatsApp shared attachment plumbing intact.
- It makes the route boundary explicit and aligned with FastAPI's native form/file model.
- It removes the brittle manual `request.form()` class-mismatch path.

TEST COVERAGE ADDED:
- Updated the app create-route test to submit a real multipart request with one file.
- The test now asserts the mocked message creation capability receives:
  - `message_text`
  - one attachment
  - filename
  - content type
  - raw file bytes

VERIFICATION:
- Focused tests:
  `.\\.venv\\Scripts\\python.exe -m pytest dcx_api_app_test.py messages\\create_authenticated_dcx_app_contact_message_test.py messages\\store_dcx_contact_message_attachment_file_object_test.py -q`
- Result: `42 passed in 1.31s`
- Broader message/file tests:
  `.\\.venv\\Scripts\\python.exe -m pytest dcx_api_app_test.py messages\\store_dcx_contact_message_attachment_file_object_test.py messages\\create_authenticated_dcx_app_contact_message_test.py messages\\read_authenticated_dcx_user_contact_message_detail_test.py messages\\read_authenticated_dcx_user_file_object_stream_by_file_uuid_test.py messages\\read_authenticated_dcx_user_contact_message_attachment_stream_test.py messages\\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py messages\\process_dcx_resend_inbound_email_received_webhook_payload_test.py -q`
- Result: `55 passed in 1.23s`

WHAT COMES NEXT:
- Re-run local app smoke tests for:
  - text + image
  - text + audio
  - text + PDF
  - mixed image + audio + document
- Then continue with email inbound attachments and any remaining provider-specific quirks.
