DCX_API
- We are working together on DCX Agentic, a full-stack building project for DCX Group. 
- Investors have signed off on the initial alpha spike and the beta MVP version.
- We are currently building the MVP version.
- This folder contains the code for the backend of the website.
- Server, webhooks, websockets, database, auth, permissions, security, etc.
- Git repo is active in this folder to record evolution of backend.
- Python venv and requirements.txt at folder root.
- This folder is deployued to production @ api.domain.com

PROJECT MAP:
- /dcx/ (project root)
    - /dcx_context/ (evolving business context for project)
        - AGENTS.md
        - [git repo]
        - /dcx_chats_ai/
        - /dcx_chats_human/
        - /dcx_evolution/
            - dcx_timeline.md (progress, stages, milestones)
            - dcx_initial_brief.md (starting point)
            - dcx_learning_paths.md (problems, opportunities, constraints, options)
            - dcx_decisions.md
            - dcx_shape.md (what project should look like)
            - dcx_tasks.md
    - /dcx_marketing/ (marketing, sales, frames, content, ads, presentations, campaigns)
        - AGENTS.md
        - [git repo]
        - /dcx_marketing_scratchpads/
        - /dcx_marketing_memory/
          - dcx_marketing_current_state.md
          - dcx_marketing_decisions.md
    - /dcx_site/ (website)
        - /dcx_admin/ (frontend: internal cms interface)
            - AGENTS.md
            - [git repo]
            - /dcx_admin_scratchpads/
            - /dcx_admin_memory/
                - dcx_admin_current_state.md
                - dcx_admin_decisions.md
        - /dcx_api/ (backend: schema, apis, webhooks, sockets)
            - AGENTS.md
            - [git repo]
            - /dcx_api_scratchpads/
            - /dcx_api_memory/
                - dcx_api_current_state.md
                - dcx_api_decisions.md
        - /dcx_app/ (frontend: user app)
            - AGENTS.md
            - [git repo]
            - /dcx_app_scratchpads/
            - /dcx_app_memory/
                - dcx_app_current_state.md
                - dcx_app_decisions.md
        - /dcx_branding/ (shared: design, branding elements, components for frontends)
            - AGENTS.md
            - [git repo]
            - /dcx_branding_scratchpads/
            - /dcx_branding_memory/
                - dcx_branding_current_state.md
                - dcx_branding_decisions.md
        - /dcx_flows/ (organisation: user, admin, data flows across front, back, connections, database)
            - AGENTS.md
            - [git repo]
            - /dcx_flows_scratchpads/
            - /dcx_flows_memory/
                - dcx_flows_current_state.md
                - dcx_flows_decisions.md
        - /dcx_public/ (frontend: main domain public site, SEO, docs, FAQ, landing pages)
            - AGENTS.md
            - [git repo]
            - /dcx_public_scratchpads/
            - /dcx_public_memory/
                - dcx_public_current_state.md
                - dcx_public_decisions.md
        - /dcx_types/ (shared: data types)
            - AGENTS.md
            - [git repo]
            - /dcx_types_scratchpads/
            - /dcx_types_memory/
                - dcx_types_current_state.md
                - dcx_types_decisions.md
    - /dcx_test/ (test ideas)
    - AGENTS.md (project root)

GENERAL INSTRUCTIONS
- you have /*_scratchpad/ folders to externalise and append your ongoing thoughts to while working on a specific task or session
- when finished, create a handoff note in /*_memory/ to provide a detailed synthesis of the task, session, problem or conclusions
- file names for memory notes: yyyy_mm_dd_file_name_here.md
- file names for scratchpad files: yyyy_mm_dd_agent_name_task_name.md

CODING INSTRUCTIONS
1. Context-native default
- Write for humans, single agents, and coordinated swarms of agents.
- Prefer locally complete semantic context over elegant indirection.
- Do not force the reader to chase through multiple files to understand what a capability does.

2. Required file and function structure
- Every code file starts with a `CONTEXT:` block explaining what the file is, why it exists, and where it fits in the system.
- Each non-trivial capability/function should carry these five sections, in this order:
  - `CONTRACT`
  - `NARRATIVE`
  - `TESTS`
  - `ERRORS`
  - `CODE`
- Prefer one main capability/function per file.
- Truly trivial private helpers may stay inline, but still need a minimal contract comment.

3. Contract rules
- Use canonical `snake_case` field names.
- Use canonical empty values: `[]`, `null`, or explicit `false` as appropriate.
- Do not use ad hoc placeholders such as `"None"` inside structured blocks.
- Every `CONTRACT` must declare:
  - preconditions
  - postconditions
  - side_effects
  - idempotent
  - retry_safe
  - async or blocking behavior
- If `side_effects` is non-empty, also declare:
  - idempotency_key
  - locks
  - contention strategy / lock strategy
- Contracts are declarations, not enforcement. The implementation must still actually enforce locking, validation, and idempotency.

4. Narrative rules
- Every `NARRATIVE` explains:
  - WHY this exists
  - WHEN TO USE it
  - WHEN NOT TO USE it
  - WHAT CAN GO WRONG
  - WHAT COMES NEXT
- Business rationale belongs in the `NARRATIVE` unless a runtime schema is explicitly versioned to carry it.

5. Test rules
- `TESTS` are the falsification layer for the contract and narrative.
- Every contract claim maps to at least one named test.
- Include tests for:
  - precondition failures
  - postcondition success
  - idempotency / deduplication
  - side effects
  - relevant error paths
- Tests specify what must be verified. The machine can decide how to execute them.
- Test files live right next to their main files

6. Error rules
- Errors must be structured, specific, and actionable.
- Every declared error includes:
  - suggested_action
  - common_causes
  - recovery_steps
  - retry_safe
- If side effects may have started, also include:
  - what_changed
  - rollback_needed
  - rollback_operation
- Use stable, explicit error codes.

7. Runtime response rules
- Success responses use the canonical wrapper shape:
  - `ok: true`
  - `data: ...`
  - `context: ...`
- Error responses use the canonical wrapper shape:
  - `ok: false`
  - `error: ...`
- Do not return raw unwrapped objects when the capability is supposed to follow the standard runtime schema.
- Responses should include enough context for both humans and agents to understand what happened and what to do next.

8. Naming rules
- Names are discovery mechanisms. Prefer long, descriptive, domain-legible names over short generic ones.
- Avoid vague names such as `process_data`, `handle_webhook`, `do_thing`, `notes.md`, or `schema.py`.
- In multi-project workspaces, use project-prefixed names for files, generated artifacts, notes, scripts, and exports.
- The longer name is cheaper than the wrong edit.
- Test files live next to their main files with *_test suffix: main_file_here.py, main_file_here_test.py

9. Concurrency and state mutation rules
- Assume multiple agents may call the same state-changing capability at the same time.
- Every state mutation must have a deduplication and idempotency strategy.
- Declare lock scope, lock duration, and contention behavior in the contract.
- Do not rely on check-then-write patterns for mutable shared state.
- Infrastructure enforces coordination; contracts make that coordination visible.

10. DRY logic, WET context
- Keep logic DRY where it helps correctness.
- Repeat semantic context locally when it improves comprehension and safe agent use.
- Comments explain why and when, not what.
- Optimize for the context window, not the file.

11. Interface and boundary rules
- Build capabilities first, then project them into UI, API, CLI, MCP, or other surfaces.
- Features and errors should work for both human users and agent users.
- Every boundary should be readable and plannable from its declared contract.

12. Review checklist before submission
- File starts with `CONTEXT:`
- Main capability/function has `CONTRACT`, `NARRATIVE`, `TESTS`, `ERRORS`, `CODE`
- Structured blocks use canonical field names and canonical empty values
- State-changing operations declare idempotency and lock behavior
- Errors are actionable and structured
- Runtime responses follow the canonical wrapper schema
- Names are descriptive and project-scoped where needed
- Comments explain why / when