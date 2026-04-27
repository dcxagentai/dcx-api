from starlette.datastructures import Headers

from routes.users.dcx_api_routes_users_me_file_object import (
    _build_dcx_private_file_response,
)


class _FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = Headers(headers or {})


def test_private_file_response_returns_full_bytes_without_range_header() -> None:
    response = _build_dcx_private_file_response(
        request=_FakeRequest(),
        content_bytes=b"audio-bytes",
        content_type="audio/mpeg",
        original_filename="voice.mp3",
    )

    assert response.status_code == 200
    assert response.body == b"audio-bytes"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "11"


def test_private_file_response_returns_partial_bytes_for_range_header() -> None:
    response = _build_dcx_private_file_response(
        request=_FakeRequest({"range": "bytes=2-6"}),
        content_bytes=b"audio-bytes",
        content_type="audio/mpeg",
        original_filename="voice.mp3",
    )

    assert response.status_code == 206
    assert response.body == b"dio-b"
    assert response.headers["content-range"] == "bytes 2-6/11"
    assert response.headers["content-length"] == "5"


def test_private_file_response_returns_416_for_unsatisfiable_range_header() -> None:
    response = _build_dcx_private_file_response(
        request=_FakeRequest({"range": "bytes=99-100"}),
        content_bytes=b"audio-bytes",
        content_type="audio/mpeg",
        original_filename="voice.mp3",
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */11"
