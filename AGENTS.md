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
        - [git repo]
        - AGENTS.md
        - PLAN.md (findings, decisions, shapes, phases)
        - WEEKS.md (evolution of project over time)
        - /dcx_human_input/
        - /dcx_project_memory/
        - /dcx_project_scratchpads/
    - /dcx_marketing/ (marketing, sales, frames, content, ads, presentations, campaigns)
        - AGENTS.md
        - [git repo]
        - /dcx_marketing_scratchpads/
        - /dcx_marketing_memory/
          - dcx_marketing_current_state.md
          - dcx_marketing_decisions.md
    - /dcx_site/ (website)
        - /dcx_flows/ (organisation: user, admin, data flows across front, back, connections, database)
            - AGENTS.md
            - [git repo]
            - /dcx_flows_scratchpads/
            - /dcx_flows_memory/
                - dcx_flows_current_state.md
                - dcx_flows_decisions.md
        - /dcx_api/ (backend: schema, apis, webhooks, sockets)
            - AGENTS.md
            - [git repo]
            - /dcx_api_scratchpads/
            - /dcx_api_memory/
                - dcx_api_current_state.md
                - dcx_api_decisions.md
        - /dcx_branding/ (shared: design, branding elements, components for frontends)
            - AGENTS.md
            - [git repo]
            - /dcx_branding_scratchpads/
            - /dcx_branding_memory/
                - dcx_branding_current_state.md
                - dcx_branding_decisions.md
        - /dcx_admin/ (frontend: internal cms interface)
            - AGENTS.md
            - [git repo]
            - /dcx_admin_scratchpads/
            - /dcx_admin_memory/
                - dcx_admin_current_state.md
                - dcx_admin_decisions.md        
        - /dcx_app/ (frontend: user app)
            - AGENTS.md
            - [git repo]
            - /dcx_app_scratchpads/
            - /dcx_app_memory/
                - dcx_app_current_state.md
                - dcx_app_decisions.md        
        - /dcx_public/ (frontend: main domain public site, SEO, docs, FAQ, landing pages)
            - AGENTS.md
            - [git repo]
            - /dcx_public_scratchpads/
            - /dcx_public_memory/
                - dcx_public_current_state.md
                - dcx_public_decisions.md
    - /dcx_test/ (test ideas)
    - AGENTS.md (project root)

GENERAL INSTRUCTIONS
- You have `/*_scratchpads/` folders to externalise and append ongoing thoughts while working on a specific task or session.
- When finished, create a handoff note in `/*_memory/` to provide a detailed synthesis of the task, session, problem, or conclusions.
- File names for memory notes: `yyyy_mm_dd_file_name_here.md`
- File names for scratchpad files: `yyyy_mm_dd_agent_name_task_name.md`

CODING INSTRUCTIONS
1. Context-native default
- Write for humans, single agents, and coordinated swarms of agents.
- Prefer locally complete semantic context over elegant indirection.
- Do not force the reader to chase through multiple files to understand what a capability does.

2. One philosophy, multiple artifact profiles
- The shared philosophy applies everywhere, but the exact structure depends on the kind of file being edited.
- Choose the profile that best matches the artifact before deciding how much structure is required.
- Main profiles:
  - Profile A: backend/domain capabilities and stateful business logic
  - Profile B: API/route boundary files
  - Profile C: frontend interactive shared logic/components
  - Profile D: frontend presentational page/theme/content files
  - Profile E: package/library repos
  - Profile F: docs/flow repos

3. Required structure by profile
- Profile A: backend/domain capabilities
  - Every code file starts with a `CONTEXT:` block explaining what the file is, why it exists, and where it fits in the system.
  - Each non-trivial capability/function should carry these five sections, in this order:
    - `CONTRACT`
    - `NARRATIVE`
    - `TESTS`
    - `ERRORS`
    - `CODE`
  - Prefer one main capability/function per file.
  - Truly trivial private helpers may stay inline, but still need a minimal contract comment.
- Profile B: API/route boundary files
  - File starts with `CONTEXT:`.
  - Every route/boundary handler that validates or mutates important state should still be readable through declared contract, narrative, tests, errors, and code.
  - Route files may group a small family of closely related handlers, but should delegate core business logic to capability files.
  - For public, auth, security-sensitive, or state-mutating route families, prefer one route file per distinct boundary action once the family grows beyond a trivial size.
  - A grouped route file is acceptable only when the grouped handlers are still genuinely small, closely related, and easier to understand together than apart.
  - If a route family contains distinct steps with different contracts, tests, side effects, or handoff points, split them into separate files.
- Profile C: frontend interactive shared logic/components
  - File starts with `CONTEXT:` when the file contains non-trivial shared state, security-sensitive logic, token handling, data fetching, form logic, or reusable business behavior.
  - Use the full five-section structure for stateful or security-sensitive shared logic.
  - Small purely presentational helper components may use lighter comments if the full template would be ceremonial.
- Profile D: frontend presentational page/theme/content files
  - Use lighter structure by default.
  - File should still make its role clear, ideally with `CONTEXT:` at the top when the purpose is not obvious.
  - Do not force the full five-section template onto large presentational files unless they contain real stateful or security-sensitive logic.
  - Keep comments focused on design intent, constraints, and why the file exists.
- Profile E: package/library repos
  - Prioritize source-of-truth clarity, export clarity, build reproducibility, and dependency correctness.
  - Use `CONTEXT:` on non-trivial source files and on build/release-sensitive files where intent is not obvious.
  - Do not add large ceremonial blocks where package integrity checks matter more than prose.
- Profile F: docs/flow repos
  - Optimize for canonical navigation, current state, decisions, and deprecation clarity.
  - Dated notes are memory/history, not the canonical operating surface.
  - Keep one current-state file and one decisions file meaningfully maintained.

4. Contract rules
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
- Contracts are declarations, not enforcement. The implementation must still actually enforce locking, validation, authorization, and idempotency.

5. Narrative rules
- Every `NARRATIVE` should explain:
  - WHY this exists
  - WHEN TO USE it
  - WHEN NOT TO USE it
  - WHAT CAN GO WRONG
  - WHAT COMES NEXT
- Business rationale belongs in the `NARRATIVE` unless a runtime schema is explicitly versioned to carry it.

6. Test rules
- `TESTS` are the falsification layer for the contract and narrative.
- Every contract claim should map to at least one named test when that claim is already implemented.
- Include tests for:
  - precondition failures
  - postcondition success
  - idempotency / deduplication
  - side effects
  - relevant error paths
- Test files live right next to their main files.
- Keep test declarations honest:
  - do not present aspirational tests as if they already exist
  - only list tests that exist now in `TESTS`
  - put missing or future coverage in `what_comes_next` or another clearly marked place

7. Error rules
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

8. Runtime response rules
- Public/API boundary responses should use one canonical wrapper shape.
- Full success wrapper:
  - `ok: true`
  - `data: ...`
  - `context: ...`
- Minimal success wrapper is allowed only when the boundary is intentionally narrow:
  - `ok: true`
  - `data: ...`
- If `context` is omitted, the omission should be deliberate and explained in the route/boundary contract or narrative.
- Canonical error wrapper:
  - `ok: false`
  - `error:`
    - `code`
    - `message`
    - `suggested_action`
- Do not return raw unwrapped objects when the capability is supposed to follow the standard runtime schema.
- Responses should include enough context for both humans and agents to understand what happened and what to do next.

9. Naming rules
- Names are discovery mechanisms. Prefer long, descriptive, domain-legible names over short generic ones.
- Avoid vague names such as `process_data`, `handle_webhook`, `do_thing`, `notes.md`, or `schema.py`.
- In multi-project workspaces, use project-prefixed names for files, generated artifacts, notes, scripts, and exports where needed.
- The longer name is cheaper than the wrong edit.
- Where practical, derive implementation file names directly from canonical flow names.
- Prefer filenames that make the flow step obvious to a human or agent without opening the file.
- In backend route files, use explicit boundary-oriented names rather than short generic names.
- Test files live next to their main files with `*_test` suffix:
  - `main_file_here.py`
  - `main_file_here_test.py`

10. Concurrency and state mutation rules
- Assume multiple agents may call the same state-changing capability at the same time.
- Every state mutation should have a deduplication and idempotency strategy.
- Declare lock scope, lock duration, and contention behavior in the contract.
- Do not rely on check-then-write patterns for mutable shared state.
- Infrastructure enforces coordination; contracts make that coordination visible.

11. Folder and file organization rules
- Organize primarily by domain or bounded context, not by technical type alone.
- As a domain grows beyond a few files, create a domain folder instead of leaving many top-level peer files.
- Route modules may group closely related boundary handlers, but should delegate domain logic to capability files.
- Prefer one main capability per file when the file is modeling real business behavior or state mutation.
- Keep adjacent tests next to the thing they verify.
- Organize implementation so important product flows can be traced from:
  - plan/flow name
  - to backend/frontend boundary
  - to concrete file names
- When a flow has distinct steps with distinct contracts or state mutations, prefer one boundary file per step.
- Example:
  - `user_signs_up_via_email`
    - `dcx_api_routes_users_signup_email.py`
    - `dcx_api_routes_users_signup_email_verify_otp.py`
    - `dcx_api_routes_users_signup_email_resend_otp.py`

12. DRY logic, WET context
- Keep logic DRY where it helps correctness.
- Repeat semantic context locally when it improves comprehension and safe agent use.
- Comments explain why and when, not what.
- Optimize for the context window, not the file.

13. Interface and boundary rules
- Build capabilities first, then project them into UI, API, CLI, MCP, or other surfaces.
- Features and errors should work for both human users and agent users.
- Every boundary should be readable and plannable from its declared contract.
- For onboarding, auth, and cross-surface flows, explicitly declare which hostname or surface owns each step.
- Flow definitions should make clear:
  - where the flow begins
  - where it continues
  - where it hands off to another subdomain or app surface
- Do not leave cross-subdomain handoff implicit.

14. Package/library rules
- Define one clear source of truth for package exports.
- Do not let committed `dist` output obscure `src` as the real source.
- Do not commit tarballs unless there is a deliberate release reason.
- Package changes should preserve source/build/export parity.
- Dependency and build reproducibility matter more than extra prose.

15. Docs/flow repo rules
- Maintain one meaningful current-state file and one meaningful decisions file.
- Use dated notes as memory/history, not as the only canonical source of truth.
- Mark superseded or outdated notes clearly when a newer canonical flow or decision exists.
- Optimize docs repos for discoverability, navigation, and restartability.

16. Review checklist before submission
- The file uses the correct artifact profile.
- File starts with `CONTEXT:` where required by the profile.
- Backend/domain/stateful/security-sensitive logic uses the full structure:
  - `CONTRACT`
  - `NARRATIVE`
  - `TESTS`
  - `ERRORS`
  - `CODE`
- Structured blocks use canonical field names and canonical empty values.
- State-changing operations declare idempotency and lock behavior.
- Errors are actionable and structured.
- Public/API boundary responses follow one canonical wrapper shape.
- `TESTS` claims match real implemented coverage.
- Names are descriptive and project-scoped where needed.
- Folders and files are organized by domain as the repo grows.
- Important flows are traceable from plan/flow name to concrete implementation files.
- Comments explain why / when.