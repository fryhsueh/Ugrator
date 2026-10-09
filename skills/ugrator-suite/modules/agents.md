# Module 3: Batch Agents Creation Specification

## Web UI Location
**Agents & Groups** > **Create Agents** > Select **📋 Quick Paste from Clipboard**

## Output Format
- Comma-delimited or Tab-delimited text block
- Header line is optional (if included, must contain `email` or `邮箱` and will be automatically skipped by the parser).

### Columns
| Column | Name | Required | Notes & Defaults |
| :---: | :--- | :--- | :--- |
| **1** | Email | Yes | Valid agent email address (e.g. `agent.one@example.com`). |
| **2** | Name / Nickname | Optional | Agent display name. If provided, both `name` and `nick_name` receive this value. |
| **3** | Password | Optional | Defaults to tenant initial password (e.g., `Pass2026`). |
| **4** | Role ID | Optional | Agent Role ID in Platform (e.g., `1694511`). If omitted, uses global default role. |
| **5** | Account Type | Optional | Agent profile type: `all`, `ticket`, `callcenter`, `im` (or Chinese aliases like `工单`, `工单客服`, `全渠道`, `呼叫中心`, `在线客服`). Defaults to Global Default Account Type. |

## Normalization & Fallback Rules
1. **Account Type / Profile Normalization**:
   - `ticket`, `工单`, `工单客服`, `工单员工` $\to$ `ticket` (Ticket Agent / 工单客服)
   - `all`, `全渠道`, `全渠道员工` $\to$ `all` (All Channels / 全渠道)
   - `callcenter`, `cc`, `呼叫中心`, `呼叫`, `电话客服` $\to$ `callcenter` (Call Center / 呼叫中心)
   - `im`, `chat`, `在线客服`, `即时通讯` $\to$ `im` (Online IM / 在线客服)
   - If omitted in paste/import, defaults to selected **Default Account Type** in the UI.
2. **Name & Nickname Pairing**:
   - If only `Name` is provided, `nick_name` automatically mirrors `Name`.
   - If only `Nickname` is provided, `Name` automatically mirrors `nick_name`.
3. **Smart Header Detection (Excel / CSV)**:
   - Recognizes header rows matching `email`/`邮箱`, `姓名`/`昵称`, `密码`, `角色`, and `员工类型`/`账号类型`/`客服类型`/`profile`/`type` (such as standard template `全渠道实施数据收集表---V1.3.xlsx`), auto-mapping columns regardless of column ordering.
4. **Rate Limiting**:
   - The platform strictly enforces API rate limits. The backend automatically throttles creation with a 2-second delay between sequential agent requests.

## Demonstration Output

```text
email, name, password, role_id, type
agent01@example.com, Agent One, Pass2026, 1694511, all
agent02@example.com, Agent Two, Pass2026, 1694511, callcenter
ticket01@example.com, Ticket Specialist, Pass2026, 1694511, ticket
im01@example.com, Live Chat Rep, Pass2026, 1694511, im
```
