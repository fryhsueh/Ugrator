---
trigger: always_on
---

# Ugrator Self-Documenting Standard

Whenever you develop, fix, or add features to Ugrator in this repository:

### 1. When Fixing/Modifying Existing Modules:
- If an input format, validation rule, or payload schema changes in `core/` or `frontend/`, you MUST immediately update the corresponding module specification file under `skills/ugrator-suite/modules/<module_name>.md`.
- Keep field length constraints, supported types, delimiter rules, and sample demonstration blocks strictly in sync with the codebase.

### 2. When Creating a BRAND-NEW Module (e.g., SLA, Knowledge Base, Routing, Webhooks):
1. **Create Spec File**: Add a new specification markdown file `skills/ugrator-suite/modules/<new_module_name>.md` detailing:
   - Module Name & Web UI tab location
   - Expected clipboard format (`tsv`, `csv`, `yaml`, or `json`)
   - Schema, limits, and valid types
   - Ready-to-copy demonstration block
2. **Register in Master Index**: Add the new module to the Master Modules Index table in `skills/ugrator-suite/SKILL.md`.
3. **Update Trigger Keywords**: Ensure the `description` frontmatter in `skills/ugrator-suite/SKILL.md` includes the new module's keywords so Antigravity recognizes queries about the new module.
4. **Commit Together**: Always commit the updated specifications in the same git commit as the code changes.
