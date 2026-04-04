"""
CONTEXT:
This file verifies the minimal DCX R2 hello-world file routes.
It keeps the manual upload, read, and delete smoke-test surface executable without requiring real
Cloudflare R2 credentials during test runs.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.files.dcx_api_routes_files_r2_hello_world as files_routes

client = TestClient(app)


class _FakeR2Client:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], dict] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self._objects[(Bucket, Key)] = {
            "Body": Body,
            "ContentType": ContentType,
        }

    def get_object(self, Bucket: str, Key: str) -> dict:
        stored_object = self._objects[(Bucket, Key)]
        return {
            "Body": BytesIO(stored_object["Body"]),
            "ContentType": stored_object["ContentType"],
        }

    def delete_object(self, Bucket: str, Key: str) -> None:
        self._objects.pop((Bucket, Key), None)


def test_hello_world_page_returns_html() -> None:
    response = client.get("/files/hello-world")

    assert response.status_code == 200
    assert "DCX R2 Hello World" in response.text
    assert "Upload image" in response.text
    assert "Delete image" in response.text


def test_hello_world_upload_read_and_delete_flow() -> None:
    fake_r2_client = _FakeR2Client()

    with patch.object(files_routes, "_build_dcx_r2_client", return_value=fake_r2_client), patch.object(
        files_routes,
        "_read_dcx_r2_bucket_name_for_alias",
        side_effect=lambda bucket_alias: {
            "app": "prompteo-dev-app-files",
            "public": "prompteo-dev-public-files",
        }[bucket_alias],
    ):
        upload_response = client.post(
            "/files/hello-world/upload",
            data={"bucket_alias": "app"},
            files={"upload_file": ("deal_photo.png", b"fake-image-bytes", "image/png")},
        )
        upload_payload = upload_response.json()

        assert upload_response.status_code == 200
        assert upload_payload["ok"] is True
        assert upload_payload["data"]["bucket_alias"] == "app"
        assert upload_payload["data"]["content_type"] == "image/png"
        assert upload_payload["data"]["object_key"].startswith("hello_world/app/")

        object_response = client.get(upload_payload["data"]["object_url"])
        assert object_response.status_code == 200
        assert object_response.content == b"fake-image-bytes"
        assert object_response.headers["content-type"] == "image/png"

        delete_response = client.delete(
            f"/files/hello-world/object/{upload_payload['data']['object_key']}",
            params={"bucket_alias": "app"},
        )
        delete_payload = delete_response.json()

        assert delete_response.status_code == 200
        assert delete_payload == {
            "ok": True,
            "data": {
                "bucket_alias": "app",
                "object_key": upload_payload["data"]["object_key"],
                "deleted": True,
            },
            "context": {
                "what_happened": "The backend requested deletion of the selected hello-world object from Cloudflare R2.",
                "side_effects_executed": [
                    f"delete_object:prompteo-dev-app-files:{upload_payload['data']['object_key']}",
                ],
                "next_steps": [
                    "Upload a fresh object if you want to repeat the smoke test.",
                ],
                "related_operations": [
                    "post_dcx_api_r2_hello_world_image_upload",
                ],
            },
        }


def test_hello_world_upload_rejects_non_image_content() -> None:
    response = client.post(
        "/files/hello-world/upload",
        data={"bucket_alias": "app"},
        files={"upload_file": ("notes.txt", b"not-an-image", "text/plain")},
    )
    payload = response.json()

    assert response.status_code == 400
    assert payload == {
        "ok": False,
        "error": {
            "code": "FILES_HELLO_WORLD_IMAGE_REQUIRED",
            "message": "Please choose an image file.",
            "suggested_action": "Select a PNG, JPG, GIF, WebP, or similar image and retry.",
        },
    }
