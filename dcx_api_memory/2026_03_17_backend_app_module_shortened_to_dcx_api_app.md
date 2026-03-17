The FastAPI application entry module was renamed from `dcx_api_fastapi_hello_world_application.py` to `dcx_api_app.py` so the local and deployment start target can stay short and obvious.

Current canonical backend start commands from the `dcx_api` repo root:

```powershell
python -m uvicorn dcx_api_app:app --reload --host 0.0.0.0 --port 8000
```

```powershell
.\.venv\Scripts\python.exe -m uvicorn dcx_api_app:app --reload --host 0.0.0.0 --port 8000
```

The adjacent test file was renamed to `dcx_api_app_test.py` to preserve the local pairing between the main app module and its test file.
