"""
CONTEXT:
This file builds stable content hashes for admin AI translation jobs.
It exists so translation rows can be compared against the current English source without
mixing that staleness logic into each content reader.
"""

from __future__ import annotations

import hashlib
import json


def build_dcx_admin_ai_translation_content_hash(fields: dict[str, str]) -> str:
    normalized_fields = {
        str(key): str(value or "")
        for key, value in sorted((fields or {}).items(), key=lambda item: str(item[0]))
    }
    serialized_fields = json.dumps(
        normalized_fields,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized_fields.encode("utf-8")).hexdigest()
