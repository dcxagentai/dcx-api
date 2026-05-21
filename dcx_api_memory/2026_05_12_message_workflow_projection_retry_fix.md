# 2026-05-12 - Message Workflow Projection Retry Fix

## Context

Client testing and local reproduction showed app-submitted messages reaching Gemini successfully, including 200 responses in Gemini logs, but still ending with orange workflow review state in the Messages detail panel. Retrying `/users/me/messages/{message_id}/retry-analysis` also returned HTTP 200 while the workflow item stayed failed.

## Root Cause

`messages/process_stored_dcx_contact_message_analysis.py` successfully called the first Gemini message-analysis prompt and, for market-topic/trade workflow items, successfully called the second projection prompt. After that second prompt returned, `_rebuild_message_workflow_projections` tried to record LLM usage with `connect=connect`, but `connect` was not in that helper's local scope.

That `NameError` was caught by the broad per-item projection exception handler and translated into a workflow projection failure. This made the backend route look healthy at HTTP level while the message stayed partially classified with failed workflow items.

## Changes

- Threaded the existing database connector from `_persist_message_analysis_result` into `_rebuild_message_workflow_projections`.
- Added a focused regression test proving a successful market-topic seed projection does not become a projection error when usage recording receives the supplied connector.
- Updated the executable file's `TESTS` declaration to name the new implemented regression coverage.

## Files

- `messages/process_stored_dcx_contact_message_analysis.py`
- `messages/process_stored_dcx_contact_message_analysis_test.py`

## Verification

- `.\.venv\Scripts\pytest.exe messages\process_stored_dcx_contact_message_analysis_test.py`
- `.\.venv\Scripts\python.exe -m compileall messages\process_stored_dcx_contact_message_analysis.py messages\process_stored_dcx_contact_message_analysis_test.py`
- Live deploy was pushed and retested on 2026-05-12. The retry/workflow pass worked again: the affected message moved from orange workflow review state to completed/projected, and the corresponding market topic was created.

## Operational Note

Existing partial/failed messages should be recoverable with the retry workflow after this fix is deployed, because `_claim_message_analysis_work` only no-ops when the message is ready and `workflow_classification_status` is already completed.

## Client-Facing Summary

The issue was not that Gemini failed to classify the message. Gemini returned successful responses, but a backend usage-accounting call added near the end of the build tried to use a database connector variable that was not available inside the workflow projection helper. The backend caught that internal error as a workflow-item projection failure, which is why API logs still showed 200 responses while the Messages screen showed an incomplete orange workflow state. The fix passes the existing database connector into that helper and adds a regression test so successful Gemini projections cannot be turned into failed workflow items by usage logging.
