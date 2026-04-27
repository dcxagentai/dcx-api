CONTEXT:
This note records the storage-key strategy decision for DCX message attachments after the first
WhatsApp image, PDF, and audio R2 ingest tests worked locally.

DECISION:
- New message attachment writes should use fully flat opaque R2 object keys.
- The object key should be `uuid4().hex` with no folder prefix and no file extension.
- The app/private bucket already provides the broad storage boundary, so adding prefixes such as
  `private/`, `messages/`, `user_id/`, or date partitions is unnecessary for the current MVP slice.

WHY:
- R2 folders are pseudo-folders rendered from key prefixes, not real filesystem directories.
- Postgres is the source of truth for meaning, ownership, message links, content type, original
  filename, access rules, and timestamps.
- Keeping the R2 key opaque avoids leaking user ids, message ids, dates, or sensitive filenames into
  the storage address.
- Existing objects continue to work because reads use the exact `object_key` stored on
  `stephen_dcx_file_objects`, rather than deriving a key from message/user/date.

IMPLEMENTATION:
- `messages/store_dcx_contact_message_attachment_file_object.py` now generates `object_key =
  uuid4().hex`.
- Existing local R2 objects under old `messages/{message_id}/...` keys can remain in place or be
  deleted manually; no migration is required for local testing.

COLLISION NOTE:
- UUID4 collisions are not mathematically impossible, but they are practically negligible for this
  workload.
- The existing database uniqueness constraint on `(storage_provider, bucket_alias, object_key)` is
  the backstop for duplicate rows.
- A future hardening pass can add retry-on-unique-conflict or conditional R2 writes if we want an
  explicit collision recovery path.
