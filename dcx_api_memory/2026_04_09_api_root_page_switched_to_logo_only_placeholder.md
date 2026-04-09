The shared `dcx_api` root page at `/` was tightened from a text placeholder to a logo-only branded placeholder.

What changed:
- Copied the canonical branding asset into `dcx_api/static/dcx_logo.png`.
- Mounted FastAPI static serving at `/static`.
- Replaced the root HTML shell so it now renders only the DCX mark image and no extra route or backend detail.

Why:
- `api.dcxagent.ai` and `files.dcxagent.ai` should not advertise route names or implementation hints.
- A quiet branded placeholder better matches the desired trust/security posture.

Verification:
- `dcx_api_app_test.py` passed after the change (`25 passed`).
