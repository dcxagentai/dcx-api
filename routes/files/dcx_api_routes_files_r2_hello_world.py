"""
CONTEXT:
This file owns the first DCX R2 hello-world HTTP surface under `/files`.
It exists to prove that the current FastAPI service can talk to Cloudflare R2, accept one image
upload, serve that object back through the backend layer, and delete it again without introducing
the full future auth, permissions, and database-backed file model yet.
"""

from __future__ import annotations

import logging
import os
from pathlib import PurePosixPath
import re
from typing import Final
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

logger = logging.getLogger("uvicorn.error")

dcx_api_routes_files_r2_hello_world_router = APIRouter(prefix="/files", tags=["files"])

_DCX_ALLOWED_BUCKET_ALIASES: Final[set[str]] = {"app", "public"}
_DCX_HELLO_WORLD_HTML: Final[str] = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>DCX R2 Hello World</title>
    <style>
      :root {
        color-scheme: light;
        font-family: Georgia, "Times New Roman", serif;
        background: #f4efe4;
        color: #1b1914;
      }
      body {
        margin: 0;
        min-height: 100vh;
        background:
          radial-gradient(circle at top left, rgba(187, 148, 87, 0.18), transparent 32rem),
          linear-gradient(180deg, #f6f1e8 0%, #efe5d3 100%);
      }
      main {
        width: min(920px, calc(100vw - 2rem));
        margin: 2rem auto;
        padding: 1.5rem;
        border: 1px solid rgba(71, 54, 30, 0.18);
        background: rgba(255, 252, 247, 0.9);
        box-shadow: 0 18px 50px rgba(56, 43, 24, 0.12);
      }
      h1 {
        margin-top: 0;
        font-size: clamp(2rem, 4vw, 3rem);
      }
      p {
        max-width: 42rem;
        line-height: 1.6;
      }
      form {
        display: grid;
        gap: 1rem;
        margin-top: 1.5rem;
      }
      label {
        display: grid;
        gap: 0.4rem;
        font-weight: 600;
      }
      input, select, button {
        font: inherit;
      }
      input, select {
        padding: 0.7rem 0.8rem;
        border: 1px solid rgba(71, 54, 30, 0.22);
        background: #fffdf8;
      }
      .button-row {
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
      }
      button {
        padding: 0.8rem 1.1rem;
        border: 0;
        cursor: pointer;
        background: #3e2b12;
        color: #f8f1e2;
      }
      button[disabled] {
        opacity: 0.55;
        cursor: wait;
      }
      .secondary {
        background: #8d6a37;
      }
      .status {
        margin-top: 1rem;
        min-height: 1.5rem;
        font-weight: 700;
      }
      .preview-card {
        display: none;
        margin-top: 1.5rem;
        padding: 1rem;
        border: 1px solid rgba(71, 54, 30, 0.18);
        background: #fffaf1;
      }
      .preview-card.visible {
        display: block;
      }
      img {
        display: block;
        width: min(100%, 520px);
        height: auto;
        margin-top: 1rem;
        border: 1px solid rgba(71, 54, 30, 0.16);
        background: #fff;
      }
      code {
        word-break: break-all;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>DCX R2 Hello World</h1>
      <p>
        This page proves the current FastAPI service can upload one image to the configured R2
        bucket, read it back through the backend layer, and delete it again.
      </p>

      <form id="hello-world-form">
        <label>
          Bucket target
          <select id="bucket-alias" name="bucket_alias">
            <option value="app">app</option>
            <option value="public">public</option>
          </select>
        </label>

        <label>
          Select image
          <input id="image-file" name="upload_file" type="file" accept="image/*" required />
        </label>

        <div class="button-row">
          <button id="upload-button" type="submit">Upload image</button>
          <button id="delete-button" class="secondary" type="button" disabled>Delete image</button>
        </div>
      </form>

      <div id="status" class="status" aria-live="polite"></div>

      <section id="preview-card" class="preview-card">
        <div><strong>Bucket:</strong> <span id="preview-bucket"></span></div>
        <div><strong>Object key:</strong> <code id="preview-key"></code></div>
        <img id="preview-image" alt="Uploaded preview" />
      </section>
    </main>

    <script>
      const form = document.getElementById("hello-world-form");
      const bucketAliasInput = document.getElementById("bucket-alias");
      const imageInput = document.getElementById("image-file");
      const uploadButton = document.getElementById("upload-button");
      const deleteButton = document.getElementById("delete-button");
      const statusNode = document.getElementById("status");
      const previewCard = document.getElementById("preview-card");
      const previewBucket = document.getElementById("preview-bucket");
      const previewKey = document.getElementById("preview-key");
      const previewImage = document.getElementById("preview-image");

      let uploadedState = null;

      function setBusy(isBusy) {
        uploadButton.disabled = isBusy;
        deleteButton.disabled = isBusy || uploadedState === null;
      }

      function setStatus(message) {
        statusNode.textContent = message;
      }

      function clearPreview() {
        uploadedState = null;
        previewCard.classList.remove("visible");
        previewBucket.textContent = "";
        previewKey.textContent = "";
        previewImage.removeAttribute("src");
        deleteButton.disabled = true;
      }

      form.addEventListener("submit", async function (event) {
        event.preventDefault();

        if (!imageInput.files || imageInput.files.length === 0) {
          setStatus("Select an image first.");
          return;
        }

        const formData = new FormData();
        formData.append("bucket_alias", bucketAliasInput.value);
        formData.append("upload_file", imageInput.files[0]);

        setBusy(true);
        setStatus("Uploading image to R2...");

        try {
          const response = await fetch("/files/hello-world/upload", {
            method: "POST",
            body: formData,
          });
          const payload = await response.json();

          if (!response.ok || payload.ok !== true) {
            throw new Error(payload.error?.message || "Upload failed.");
          }

          uploadedState = payload.data;
          previewBucket.textContent = payload.data.bucket_alias;
          previewKey.textContent = payload.data.object_key;
          previewImage.src = payload.data.object_url + "&t=" + Date.now();
          previewCard.classList.add("visible");
          deleteButton.disabled = false;
          setStatus("Upload complete.");
        } catch (error) {
          clearPreview();
          setStatus(error.message || "Upload failed.");
        } finally {
          setBusy(false);
        }
      });

      deleteButton.addEventListener("click", async function () {
        if (!uploadedState) {
          return;
        }

        setBusy(true);
        setStatus("Deleting image from R2...");

        try {
          const response = await fetch(uploadedState.object_url, { method: "DELETE" });
          const payload = await response.json();

          if (!response.ok || payload.ok !== true) {
            throw new Error(payload.error?.message || "Delete failed.");
          }

          clearPreview();
          imageInput.value = "";
          setStatus("Delete complete.");
        } catch (error) {
          setStatus(error.message || "Delete failed.");
        } finally {
          setBusy(false);
        }
      });
    </script>
  </body>
</html>
"""


@dcx_api_routes_files_r2_hello_world_router.get("/hello-world")
def get_dcx_api_r2_hello_world_page() -> HTMLResponse:
    """
    CONTRACT:
      preconditions:
        - The FastAPI service is running and the files router is mounted.
      postconditions:
        - Returns one static HTML page with a minimal upload, preview, and delete interface.
        - Does not contact R2 or mutate storage state.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why:
        - This exists as the quickest manual proof that `files.dcxagent.ai` can host a human-usable R2 smoke test without waiting for the real app UI.
      when_to_use:
        - Use it during early local and Render media plumbing checks.
      when_not_to_use:
        - Do not treat this as the future DCX app media UI.
        - Do not expose it broadly once real auth-protected file flows exist.
      what_can_go_wrong:
        - The later upload and delete calls can still fail if R2 credentials or bucket names are missing.
      what_comes_next:
        - Replace this manual smoke-test surface with proper app/admin flows backed by canonical file records and permissions.

    TESTS:
      - hello_world_page_returns_html
      - hello_world_page_mentions_upload_and_delete

    ERRORS:
      - FILES_HELLO_WORLD_PAGE_UNAVAILABLE:
          suggested_action: Confirm the files router is still mounted in the FastAPI app.
          common_causes:
            - router import removed
            - route prefix changed unexpectedly
          recovery_steps:
            - Re-check dcx_api_app.py router wiring.
            - Retry the page request.
          retry_safe: true

    CODE:
    """
    return HTMLResponse(_DCX_HELLO_WORLD_HTML)


@dcx_api_routes_files_r2_hello_world_router.post("/hello-world/upload")
async def post_dcx_api_r2_hello_world_image_upload(
    bucket_alias: str = Form(...),
    upload_file: UploadFile = File(...),
) -> JSONResponse:
    """
    CONTRACT:
      preconditions:
        - The request provides one bucket alias of `app` or `public`.
        - The request provides one image file in multipart form data.
        - The configured R2 credentials and bucket names are present in the environment.
      postconditions:
        - Uploads one image object to the selected configured R2 bucket.
        - Returns one canonical success wrapper with the object key and backend-served object URL.
      side_effects:
        - writes one object to Cloudflare R2
      idempotent: false
      retry_safe: false
      async: true
      idempotency_key: null
      locks: []
      contention_strategy: generate a fresh object key for every upload rather than trying to deduplicate hello-world test uploads

    NARRATIVE:
      why:
        - This exists to prove the backend can perform the first real write into R2 before we introduce the full file schema and upload-intent flow.
      when_to_use:
        - Use it for manual smoke tests only.
      when_not_to_use:
        - Do not use it as the real product upload contract.
        - Do not use it for sensitive production documents.
      what_can_go_wrong:
        - Missing credentials, unknown bucket alias, bad content type, or R2 API failure can all reject the upload.
      what_comes_next:
        - Move from this direct hello-world upload into canonical `dcx_files` rows and permission-aware upload intents.

    TESTS:
      - hello_world_upload_returns_backend_object_url
      - hello_world_upload_rejects_non_image_content

    ERRORS:
      - FILES_HELLO_WORLD_BUCKET_ALIAS_INVALID:
          suggested_action: Choose either the app or public bucket target.
          common_causes:
            - unsupported bucket alias
            - tampered form payload
          recovery_steps:
            - Reload the hello-world page.
            - Retry with a valid bucket option.
          retry_safe: true
      - FILES_HELLO_WORLD_IMAGE_REQUIRED:
          suggested_action: Select a real image file and try again.
          common_causes:
            - no file uploaded
            - unsupported file type
          recovery_steps:
            - Choose a PNG, JPG, GIF, WebP, or similar image file.
            - Retry the upload.
          retry_safe: true
      - FILES_HELLO_WORLD_R2_CONFIGURATION_MISSING:
          suggested_action: Set the required R2 environment variables before retrying.
          common_causes:
            - missing account id
            - missing access key
            - missing secret key
            - missing bucket env vars
          recovery_steps:
            - Re-check `.env` or Render environment variables.
            - Restart the backend.
          retry_safe: true
      - FILES_HELLO_WORLD_UPLOAD_FAILED:
          suggested_action: Confirm the bucket exists and the configured credentials can write to it.
          common_causes:
            - wrong bucket name
            - invalid credentials
            - temporary R2 API failure
          recovery_steps:
            - Re-check bucket names and credentials.
            - Retry the upload.
          retry_safe: true

    CODE:
    """
    try:
        if upload_file.filename is None or upload_file.filename.strip() == "":
            raise RuntimeError("FILES_HELLO_WORLD_IMAGE_REQUIRED")

        normalized_content_type = (upload_file.content_type or "").strip().lower()
        if not normalized_content_type.startswith("image/"):
            raise RuntimeError("FILES_HELLO_WORLD_IMAGE_REQUIRED")

        selected_bucket_name = _read_dcx_r2_bucket_name_for_alias(bucket_alias)

        sanitized_filename = _sanitize_hello_world_filename(upload_file.filename)
        object_key = (
            f"hello_world/{bucket_alias}/{uuid4().hex}_{sanitized_filename}"
            if sanitized_filename != ""
            else f"hello_world/{bucket_alias}/{uuid4().hex}"
        )
        image_bytes = await upload_file.read()
        if len(image_bytes) == 0:
            raise RuntimeError("FILES_HELLO_WORLD_IMAGE_REQUIRED")

        _build_dcx_r2_client().put_object(
            Bucket=selected_bucket_name,
            Key=object_key,
            Body=image_bytes,
            ContentType=normalized_content_type,
        )
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": _map_files_hello_world_error(str(runtime_error)),
            },
        )
    except ClientError as client_error:
        logger.info(
            "files_hello_world_upload_failed bucket_alias=%s error=%s",
            bucket_alias,
            str(client_error),
        )
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": _map_files_hello_world_error("FILES_HELLO_WORLD_UPLOAD_FAILED"),
            },
        )

    return JSONResponse(
        content={
            "ok": True,
            "data": {
                "bucket_alias": bucket_alias,
                "object_key": object_key,
                "content_type": normalized_content_type,
                "object_url": (
                    f"/files/hello-world/object/{quote(object_key, safe='/')}"
                    f"?bucket_alias={quote(bucket_alias, safe='')}"
                ),
            },
            "context": {
                "what_happened": "The backend wrote one test image to the configured Cloudflare R2 bucket.",
                "side_effects_executed": [
                    f"put_object:{selected_bucket_name}:{object_key}",
                ],
                "next_steps": [
                    "Load the returned object_url through the backend read route.",
                    "Delete the object again once the smoke test is complete.",
                ],
                "related_operations": [
                    "get_dcx_api_r2_hello_world_object",
                    "delete_dcx_api_r2_hello_world_object",
                ],
            },
        }
    )


@dcx_api_routes_files_r2_hello_world_router.get("/hello-world/object/{object_key:path}")
def get_dcx_api_r2_hello_world_object(
    object_key: str,
    bucket_alias: str,
) -> Response:
    """
    CONTRACT:
      preconditions:
        - The request provides one bucket alias of `app` or `public`.
        - The provided object key refers to a previously uploaded hello-world object.
      postconditions:
        - Returns the object bytes through the backend layer when the object exists.
        - Returns a canonical error wrapper when the object cannot be read.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why:
        - This exists so the smoke test proves the future delivery shape too: browsers ask DCX for the file rather than talking directly to R2.
      when_to_use:
        - Use it to preview the uploaded hello-world image.
      when_not_to_use:
        - Do not treat this unauthenticated object read route as the final private-file delivery contract.
      what_can_go_wrong:
        - Unknown bucket alias, missing credentials, missing object, or R2 read errors can all fail the request.
      what_comes_next:
        - Later this route shape should evolve into an authorization-aware file delivery boundary.

    TESTS:
      - hello_world_object_route_returns_uploaded_bytes
      - hello_world_object_route_returns_not_found_wrapper_when_missing

    ERRORS:
      - FILES_HELLO_WORLD_OBJECT_READ_FAILED:
          suggested_action: Confirm the object still exists in the selected bucket and retry.
          common_causes:
            - object key typo
            - object already deleted
            - wrong bucket alias
          recovery_steps:
            - Re-upload the test image if needed.
            - Retry with the returned object key.
          retry_safe: true

    CODE:
    """
    try:
        selected_bucket_name = _read_dcx_r2_bucket_name_for_alias(bucket_alias)
        r2_object_response = _build_dcx_r2_client().get_object(
            Bucket=selected_bucket_name,
            Key=object_key,
        )
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": _map_files_hello_world_error(str(runtime_error)),
            },
        )
    except ClientError as client_error:
        error_code = client_error.response.get("Error", {}).get("Code", "")
        logger.info(
            "files_hello_world_object_read_failed bucket_alias=%s object_key=%s error_code=%s",
            bucket_alias,
            object_key,
            error_code,
        )
        return JSONResponse(
            status_code=404 if error_code in {"NoSuchKey", "404"} else 502,
            content={
                "ok": False,
                "error": _map_files_hello_world_error("FILES_HELLO_WORLD_OBJECT_READ_FAILED"),
            },
        )

    body_stream = r2_object_response["Body"]
    object_bytes = body_stream.read()
    media_type = r2_object_response.get("ContentType", "application/octet-stream")
    return Response(
        content=object_bytes,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
        },
    )


@dcx_api_routes_files_r2_hello_world_router.delete("/hello-world/object/{object_key:path}")
def delete_dcx_api_r2_hello_world_object(
    object_key: str,
    bucket_alias: str,
) -> JSONResponse:
    """
    CONTRACT:
      preconditions:
        - The request provides one bucket alias of `app` or `public`.
        - The provided object key refers to the hello-world object that should be removed.
      postconditions:
        - Deletes the selected object from the configured R2 bucket.
        - Returns one canonical success wrapper even if the object was already absent.
      side_effects:
        - deletes one object from Cloudflare R2 if it exists
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: delete_hello_world_object:{bucket_alias}:{object_key}
      locks: []
      contention_strategy: rely on object-key uniqueness and idempotent delete semantics rather than trying to coordinate deletes

    NARRATIVE:
      why:
        - This exists to complete the hello-world storage loop and avoid leaving test objects behind after every smoke test.
      when_to_use:
        - Use it from the hello-world test page after confirming upload and read behavior.
      when_not_to_use:
        - Do not use it as the future audited delete contract for real user files.
      what_can_go_wrong:
        - Missing credentials or a bad bucket alias can fail the delete.
      what_comes_next:
        - Replace this with permission-aware soft-delete logic once canonical file records exist.

    TESTS:
      - hello_world_delete_route_removes_uploaded_object
      - hello_world_delete_route_is_idempotent_for_missing_object

    ERRORS:
      - FILES_HELLO_WORLD_DELETE_FAILED:
          suggested_action: Confirm the bucket exists and the configured credentials can delete from it.
          common_causes:
            - wrong bucket name
            - invalid credentials
            - temporary R2 API failure
          recovery_steps:
            - Re-check credentials and bucket env vars.
            - Retry the delete.
          retry_safe: true

    CODE:
    """
    try:
        selected_bucket_name = _read_dcx_r2_bucket_name_for_alias(bucket_alias)
        _build_dcx_r2_client().delete_object(
            Bucket=selected_bucket_name,
            Key=object_key,
        )
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": _map_files_hello_world_error(str(runtime_error)),
            },
        )
    except ClientError as client_error:
        logger.info(
            "files_hello_world_delete_failed bucket_alias=%s object_key=%s error=%s",
            bucket_alias,
            object_key,
            str(client_error),
        )
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": _map_files_hello_world_error("FILES_HELLO_WORLD_DELETE_FAILED"),
            },
        )

    return JSONResponse(
        content={
            "ok": True,
            "data": {
                "bucket_alias": bucket_alias,
                "object_key": object_key,
                "deleted": True,
            },
            "context": {
                "what_happened": "The backend requested deletion of the selected hello-world object from Cloudflare R2.",
                "side_effects_executed": [
                    f"delete_object:{selected_bucket_name}:{object_key}",
                ],
                "next_steps": [
                    "Upload a fresh object if you want to repeat the smoke test.",
                ],
                "related_operations": [
                    "post_dcx_api_r2_hello_world_image_upload",
                ],
            },
        }
    )


def _sanitize_hello_world_filename(filename: str) -> str:
    """Minimal contract: keep only simple path-safe filename characters for hello-world object keys."""
    safe_name = PurePosixPath(filename).name.strip()
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", safe_name).strip("._")


def _read_dcx_r2_bucket_name_for_alias(bucket_alias: str) -> str:
    """Minimal contract: map one allowed hello-world bucket alias to its configured concrete bucket name."""
    normalized_bucket_alias = bucket_alias.strip().lower()
    if normalized_bucket_alias not in _DCX_ALLOWED_BUCKET_ALIASES:
        raise RuntimeError("FILES_HELLO_WORLD_BUCKET_ALIAS_INVALID")

    bucket_env_var_name = (
        "DCX_R2_APP_BUCKET_NAME"
        if normalized_bucket_alias == "app"
        else "DCX_R2_PUBLIC_BUCKET_NAME"
    )
    bucket_name = os.getenv(bucket_env_var_name, "").strip()
    if bucket_name == "":
        raise RuntimeError("FILES_HELLO_WORLD_R2_CONFIGURATION_MISSING")

    return bucket_name


def _read_dcx_r2_s3_endpoint_url() -> str:
    """Minimal contract: return the configured R2 S3 endpoint or derive it from the Cloudflare account id."""
    configured_endpoint_url = os.getenv("DCX_R2_S3_ENDPOINT_URL", "").strip()
    if configured_endpoint_url != "":
        return configured_endpoint_url

    account_id = os.getenv("DCX_R2_ACCOUNT_ID", "").strip()
    if account_id == "":
        raise RuntimeError("FILES_HELLO_WORLD_R2_CONFIGURATION_MISSING")

    return f"https://{account_id}.r2.cloudflarestorage.com"


def _build_dcx_r2_client() -> BaseClient:
    """Minimal contract: create one boto3 S3-compatible client for Cloudflare R2 using the configured env vars."""
    access_key_id = os.getenv("DCX_R2_ACCESS_KEY_ID", "").strip()
    secret_access_key = os.getenv("DCX_R2_SECRET_ACCESS_KEY", "").strip()
    if access_key_id == "" or secret_access_key == "":
        raise RuntimeError("FILES_HELLO_WORLD_R2_CONFIGURATION_MISSING")

    return boto3.client(
        "s3",
        endpoint_url=_read_dcx_r2_s3_endpoint_url(),
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )


def _map_files_hello_world_error(error_code: str) -> dict:
    if error_code == "FILES_HELLO_WORLD_BUCKET_ALIAS_INVALID":
        return {
            "code": error_code,
            "message": "That bucket option is not valid.",
            "suggested_action": "Choose the app or public bucket and try again.",
        }

    if error_code == "FILES_HELLO_WORLD_IMAGE_REQUIRED":
        return {
            "code": error_code,
            "message": "Please choose an image file.",
            "suggested_action": "Select a PNG, JPG, GIF, WebP, or similar image and retry.",
        }

    if error_code == "FILES_HELLO_WORLD_OBJECT_READ_FAILED":
        return {
            "code": error_code,
            "message": "We could not read that object from storage.",
            "suggested_action": "Upload the image again or confirm the object key still exists.",
        }

    if error_code == "FILES_HELLO_WORLD_DELETE_FAILED":
        return {
            "code": error_code,
            "message": "We could not delete that object from storage.",
            "suggested_action": "Retry the delete after checking the bucket configuration.",
        }

    if error_code in {
        "FILES_HELLO_WORLD_R2_CONFIGURATION_MISSING",
        "FILES_HELLO_WORLD_UPLOAD_FAILED",
    }:
        return {
            "code": error_code,
            "message": "The R2 hello-world storage flow is not configured correctly.",
            "suggested_action": "Check the R2 credentials, endpoint, and bucket names, then retry.",
        }

    return {
        "code": "FILES_HELLO_WORLD_REQUEST_INVALID",
        "message": "We could not complete that files request.",
        "suggested_action": "Reload the page and try again.",
    }
