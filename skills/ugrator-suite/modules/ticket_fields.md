# Module 1: Ticket Custom Fields Specification

## Web UI Location
**Tickets** > **Create Custom Fields** > Select **📋 Quick Paste from Clipboard**

## Output Format
- Code block labeled `tsv`
- Separated by literal **Tab characters (`\t`)**, never pipes (`|`) or spaces.
- **NO header row**.

### Columns
| Column | Name | Type | Notes |
| :---: | :--- | :--- | :--- |
| **1** | Field Name | String | Max **30 characters**. Punctuation and numbering prefixes stripped. |
| **2** | Field Type | Identifier | Strictly one of: `text`, `multiline` (aliases: `area_text`, `textarea`), `date`, `drop_list` |
| **3** | Options | String | Comma-separated discrete options for `drop_list`. **Leave completely empty for `text`, `multiline`, and `date`**. |
| **4** | Placeholder *(Optional)* | String | Input guide / hint text (mapped to platform API `text_field.placeholder`). |
| **5** | Description *(Optional)* | String | Explanatory comment/description (mapped to platform API `comment`). Distinguishes identical field titles and explains usage. |
| **6** | Persona *(Optional)* | String | Target persona / audience (e.g. `Agent`, `Distributor`, `Internal`, or `All`). Used by Ugrator's Role Visibility Rules to automatically set field permissions (making fields invisible to specified agent roles). Defaults to `All` if omitted. |

### Universal Layouts Supported by Quick Paste
- **6 Columns (Full format)**: `Field Name \t Type \t Options \t Placeholder \t Description \t Persona`
- **5 Columns**:
  - If Column 5 matches a known persona (`Agent`, `Distributor`, `Internal`, `All`): `Field Name \t Type \t Options \t Description \t Persona`
  - Otherwise: `Field Name \t Type \t Options \t Placeholder \t Description` (Persona defaults to `All`).
- **4 Columns**:
  - If Column 4 matches a known persona: treated as `Persona` (Description & Placeholder are empty).
  - Otherwise: treated as `Description` (Persona defaults to `All`).
- **3 Columns (Simple format)**: `Field Name \t Type \t Options` (Placeholder & Description empty, Persona defaults to `All`).

## Rules & Constraints
1. **Length Limit**: Maximum 30 characters for the field name.
2. **Options Normalization**:
   - Separate options with commas (`,`).
   - Trim whitespace around options.
   - Deduplicate identical options.
3. **Multiline (`area_text`) Support**:
   - Type identifier: `multiline`, `area_text`, `textarea`, `多行文本`, or `多行`.
   - Created via `POST /cs/ts/api/text_fields` with `"content_type": "area_text"`, `"init_height": 2`.
4. **Placeholder & Description Mapping**:
   - The placeholder column is sent directly to `text_field.placeholder` (input hint displayed inside the field).
   - The description column is sent directly to the platform API as `comment` (`text_field.comment` and `select_field.comment`).
5. **Role Permission & Persona Rules**:
   - Fields marked with specific personas (e.g. `Distributor`) can be automatically hidden from opposing roles (e.g. Call Center `Agent`) using the **Role Visibility Rules** panel or Role Segregation preset.
   - For non-dropdown fields (`text`, `multiline`, `date`) where column 3 is omitted, tab delimiters must still align properly: `Field Name \t multiline \t \t Hint \t Description \t Persona`.
6. **Skipping / Unsupported Types**:
   - Multi-select checkboxes (`checkbox`), cascading trees (`chained_droplist`), file attachments, and rich text areas are **NOT** supported by Quick Paste.
   - Skip them and list them in the "Skipped / Unsupported Fields & Warnings" section with manual configuration guidance in Admin Console.

## Demonstration Output

```tsv
Customer Name	text			Please enter customer name	Customer full legal name	Agent
Incident Details	multiline		Briefly describe the occurrence	Detailed customer problem summary	All
Purchase Date	date			Select purchase date	Date of product purchase	All
Product Model	drop_list	Model Alpha, Model Beta, Model Pro		Product model code	All
Distributor Defect Code	text			Enter dealer defect code	Dealer internal repair defect identifier	Distributor
Issue Category	drop_list	Engine, Transmission, Electrical, Body, Other		Primary issue classification	All
Distributor Claim Status	drop_list	Pending, Approved, Rejected		Warranty claim review status	Distributor
Internal Quality Check	drop_list	Passed, Pending, Failed		Factory audit status	Internal
```
