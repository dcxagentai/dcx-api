"""
CONTEXT:
This file normalizes one verified Meta WhatsApp webhook payload into inbound message envelopes.
It exists so route code does not need to understand the nested provider payload shape directly.
"""

from __future__ import annotations

from typing import Any


def read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload(
    webhook_payload: dict,
) -> list[dict[str, Any]]:
    """
    CONTRACT:
      preconditions:
        - webhook_payload is one verified parsed Meta WhatsApp webhook JSON object.
      postconditions:
        - Returns one list of canonical inbound message envelopes, possibly empty.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The inbound WhatsApp route should not duplicate nested payload walking each time provider examples evolve.
      WHEN TO USE it:
        - Use it after signature verification and before canonical message ingestion.
      WHEN NOT TO USE it:
        - Do not use it for outbound message status updates or browser-originated messages.
      WHAT CAN GO WRONG:
        - The payload may not contain inbound messages.
      WHAT COMES NEXT:
        - Media-specific retrieval can use the attachment descriptors returned on image, audio, and
          document envelopes.

    TESTS:
      - none yet in this first webhook-ingest pass

    ERRORS:
      - none

    CODE:
    """
    inbound_message_envelopes: list[dict[str, Any]] = []
    supported_visible_message_types = {"text", "image", "audio", "document"}

    for entry in webhook_payload.get("entry", []):
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []):
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
            business_phone_number = metadata.get("display_phone_number") or metadata.get("phone_number_id")
            contacts = value.get("contacts") if isinstance(value.get("contacts"), list) else []
            for message in value.get("messages", []):
                if not isinstance(message, dict):
                    continue
                raw_message_type = (message.get("type") or "").strip().lower()
                if raw_message_type == "":
                    continue

                raw_text_content = ""
                if raw_message_type == "text" and isinstance(message.get("text"), dict):
                    raw_text_content = (message["text"].get("body") or "").strip()
                elif raw_message_type == "image" and isinstance(message.get("image"), dict):
                    raw_text_content = (message["image"].get("caption") or "").strip()
                elif raw_message_type == "document" and isinstance(message.get("document"), dict):
                    raw_text_content = (message["document"].get("caption") or "").strip()
                elif raw_message_type == "button" and isinstance(message.get("button"), dict):
                    raw_text_content = (message["button"].get("text") or "").strip()
                elif raw_message_type == "interactive" and isinstance(message.get("interactive"), dict):
                    raw_text_content = _read_dcx_meta_whatsapp_interactive_text(message["interactive"])

                attachment_descriptors = _read_dcx_meta_whatsapp_attachment_descriptors_for_message(message)
                if (
                    raw_message_type not in supported_visible_message_types
                    and raw_text_content == ""
                    and len(attachment_descriptors) == 0
                ):
                    continue

                provider_message_id = (message.get("id") or "").strip()
                if provider_message_id == "":
                    continue

                message_format = raw_message_type if raw_message_type in supported_visible_message_types else "mixed"
                contact_profile_name = None
                if len(contacts) > 0 and isinstance(contacts[0], dict):
                    profile = contacts[0].get("profile") if isinstance(contacts[0].get("profile"), dict) else {}
                    contact_profile_name = profile.get("name")

                inbound_message_envelopes.append(
                    {
                        "provider_message_id": provider_message_id,
                        "source_handle": str(message.get("from") or "").strip(),
                        "target_handle": str(business_phone_number or "").strip(),
                        "message_format": message_format,
                        "message_subject": "",
                        "raw_text_content": raw_text_content,
                        "received_at_ts_ms": _read_dcx_meta_whatsapp_timestamp_ms(message.get("timestamp")),
                        "should_mark_read": True,
                        "message_metadata_json": {
                            "meta_message_type": raw_message_type,
                            "meta_contact_profile_name": contact_profile_name,
                            "meta_context": message.get("context") if isinstance(message.get("context"), dict) else {},
                            "meta_contacts": contacts,
                        },
                        "attachment_descriptors": attachment_descriptors,
                    }
                )

    return inbound_message_envelopes


def _read_dcx_meta_whatsapp_interactive_text(interactive_payload: dict) -> str:
    button_reply = interactive_payload.get("button_reply") if isinstance(interactive_payload.get("button_reply"), dict) else None
    if button_reply is not None:
        return (button_reply.get("title") or button_reply.get("id") or "").strip()

    list_reply = interactive_payload.get("list_reply") if isinstance(interactive_payload.get("list_reply"), dict) else None
    if list_reply is not None:
        return (list_reply.get("title") or list_reply.get("id") or "").strip()

    return ""


def _read_dcx_meta_whatsapp_attachment_descriptors_for_message(message: dict) -> list[dict[str, Any]]:
    raw_message_type = (message.get("type") or "").strip().lower()
    if raw_message_type == "image" and isinstance(message.get("image"), dict):
        image_payload = message["image"]
        return [
            {
                "provider_media_id": (image_payload.get("id") or "").strip() or None,
                "content_type": (image_payload.get("mime_type") or "").strip().lower() or None,
                "original_filename": None,
            }
        ]

    if raw_message_type == "audio" and isinstance(message.get("audio"), dict):
        audio_payload = message["audio"]
        return [
            {
                "provider_media_id": (audio_payload.get("id") or "").strip() or None,
                "content_type": (audio_payload.get("mime_type") or "").strip().lower() or None,
                "original_filename": None,
            }
        ]

    if raw_message_type == "document" and isinstance(message.get("document"), dict):
        document_payload = message["document"]
        return [
            {
                "provider_media_id": (document_payload.get("id") or "").strip() or None,
                "content_type": (document_payload.get("mime_type") or "").strip().lower() or None,
                "original_filename": (document_payload.get("filename") or "").strip() or None,
            }
        ]

    return []


def _read_dcx_meta_whatsapp_timestamp_ms(raw_timestamp: Any) -> int:
    if isinstance(raw_timestamp, str) and raw_timestamp.isdigit():
        return int(raw_timestamp) * 1000

    return 0
