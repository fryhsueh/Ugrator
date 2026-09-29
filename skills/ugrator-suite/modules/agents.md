# Module 3: Batch Agents Creation Specification

## Web UI Location
**Agents & Groups** > **Create Agents** > Select **📋 Quick Paste from Clipboard**

## Output Format
- Comma-delimited or Tab-delimited text block
- Header line is optional (if included, must contain `email` or `邮箱` and will be automatically skipped by the parser).

### Columns
| Column | Name | Required | Notes & Defaults |
| :---: | :--- | :---: | :--- |
| **1** | Email | Yes | Valid agent email address (e.g. `agent.one@example.com`). |
| **2** | Name / Nickname | Optional | Agent display name. If provided, both `name` and `nick_name` receive this value. |
| **3** | Password | Optional | Defaults to tenant initial password (e.g., `Pass2026`). |
| **4** | Role ID | Optional | Agent Role ID in Platform (e.g., `1694511`). If omitted, uses global default role. |

## Normalization & Fallback Rules
1. **Name & Nickname Pairing**:
   - If only `Name` is provided, `nick_name` automatically mirrors `Name`.
   - If only `Nickname` is provided, `Name` automatically mirrors `nick_name`.
2. **Rate Limiting**:
   - The platform strictly enforces API rate limits. The backend automatically throttles creation with a 2-second delay between sequential agent requests.

## Demonstration Output

```text
email, name, password, role_id
agent01@example.com, Agent One, Pass2026, 1694511
agent02@example.com, Agent Two, Pass2026, 1694511
support01@example.com, Support One, Pass2026, 1694511
```
