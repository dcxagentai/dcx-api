import routes.admin.dcx_api_routes_admin_jobs_email_cron_run as email_cron_route
from dcx_api_app import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_admin_jobs_email_cron_run_requires_cron_secret_configuration(monkeypatch) -> None:
    monkeypatch.delenv("DCX_CRON_SECRET", raising=False)

    response = client.post("/admin/jobs/email-cron/run")
    payload = response.json()

    assert response.status_code == 500
    assert payload["ok"] is False
    assert payload["error"]["code"] == "API_DCX_CRON_SECRET_NOT_CONFIGURED"


def test_admin_jobs_email_cron_run_rejects_missing_or_wrong_secret(monkeypatch) -> None:
    monkeypatch.setenv("DCX_CRON_SECRET", "correct-secret")

    response = client.post(
        "/admin/jobs/email-cron/run",
        headers={"X-DCX-CRON-SECRET": "wrong-secret"},
    )
    payload = response.json()

    assert response.status_code == 401
    assert payload["ok"] is False
    assert payload["error"]["code"] == "API_DCX_CRON_SECRET_INVALID"


def test_admin_jobs_email_cron_run_returns_due_email_job_summary(monkeypatch) -> None:
    monkeypatch.setenv("DCX_CRON_SECRET", "correct-secret")
    monkeypatch.setattr(
        email_cron_route,
        "_run_due_dcx_email_jobs",
        lambda: {
            "ok": True,
            "sequence_schedule_result": {"status": "idle"},
            "dispatch_results": [{"status": "idle"}],
        },
    )

    response = client.post(
        "/admin/jobs/email-cron/run",
        headers={"X-DCX-CRON-SECRET": "correct-secret"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["sequence_schedule_result"]["status"] == "idle"
    assert payload["data"]["dispatch_results"][0]["status"] == "idle"
    assert payload["context"]["auth_mode"] == "cron_secret"
