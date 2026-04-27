from files import build_dcx_r2_s3_client as r2_client_module


def test_builds_r2_client_with_bounded_timeouts_and_retry_config(monkeypatch) -> None:
    captured_client_kwargs = {}

    def _fake_boto3_client(service_name: str, **kwargs):
        captured_client_kwargs["service_name"] = service_name
        captured_client_kwargs.update(kwargs)
        return {"client": "ok"}

    monkeypatch.setenv("DCX_R2_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("DCX_R2_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setenv("DCX_R2_ACCOUNT_ID", "test-account")
    monkeypatch.delenv("DCX_R2_S3_ENDPOINT_URL", raising=False)
    monkeypatch.setattr(r2_client_module.boto3, "client", _fake_boto3_client)

    result = r2_client_module.build_dcx_r2_s3_client()

    assert result == {"client": "ok"}
    assert captured_client_kwargs["service_name"] == "s3"
    assert captured_client_kwargs["endpoint_url"] == "https://test-account.r2.cloudflarestorage.com"
    assert captured_client_kwargs["config"].connect_timeout == 5
    assert captured_client_kwargs["config"].read_timeout == 15
    assert captured_client_kwargs["config"].retries["max_attempts"] == 2
