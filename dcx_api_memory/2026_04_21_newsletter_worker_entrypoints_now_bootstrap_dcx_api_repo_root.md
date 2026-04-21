# Context

Local newsletter worker execution failed when launched from outside the `dcx_api` folder with:

- `ModuleNotFoundError: No module named 'content'`

The failure was not in newsletter sending itself. It was the entrypoint scripts assuming the current shell location already put the `dcx_api` repo root on Python's import path.

# What Changed

- `system/background_jobs/run_dcx_newsletter_resend_dispatch_worker.py`
  - now inserts the `dcx_api` repo root onto `sys.path` before importing `content.*`
- `system/background_jobs/run_one_due_dcx_newsletter_resend_dispatch_pass.py`
  - now does the same bootstrap step

# Why This Helps

- Both worker entrypoints can now be launched from higher-level folders or external venv shells without depending on the caller's current working directory.
- This matches the real local operator path more closely, because the command is often run from a general project shell rather than from inside `dcx_api`.

# Verification

- Running the one-pass entrypoint with the user's external venv/interpreter style now returns a normal payload instead of a `ModuleNotFoundError`.
- Running the long worker entrypoint no longer fails immediately on import; it keeps looping until manually stopped.
