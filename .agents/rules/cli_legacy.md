# CLI Status: Legacy (Do Not Update)

## Policy
The Command Line Interface (`migrator.py`) is officially **LEGACY** and deprecated.

## Directives for Developers & AI Agents
1. **No New Features in CLI**: Do not add new CLI flags, arguments, or subparsers to `migrator.py`.
2. **Focus on Web UI & Core Library**:
   - All active development, UI workflows, and user-facing features belong in `frontend/` and `core/router.py`.
   - All business logic and automation routines belong in `core/` (`core/ivr.py`, `core/voice.py`, `core/fields.py`, `core/templates.py`, `core/groups.py`, `core/assign.py`, `core/browser.py`).
3. **Web UI Independence**: The Web UI (`server.py` + `frontend/`) does **not** rely on `migrator.py` in any way.
