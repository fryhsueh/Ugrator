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
| **2** | Field Type | Identifier | Strictly one of: `text`, `date`, `drop_list` |
| **3** | Options | String | Comma-separated discrete options for `drop_list`. **Leave completely empty for `text` and `date`**. |
| **4** | Description *(Optional)* | String | Explanatory comment/description (mapped to platform API `comment`). Distinguishes identical field titles and explains usage. |
| **5** | Persona *(Optional)* | String | Target persona / audience (e.g. `Agent`, `Distributor`, `Internal`, or `All`). Used by Ugrator's Role Visibility Rules to automatically set field permissions (making fields invisible to specified agent roles). Defaults to `All` if omitted. |

### Universal Layouts Supported by Quick Paste
- **5 Columns (Full format)**: `Field Name \t Type \t Options \t Description \t Persona`
- **4 Columns**:
  - If Column 4 matches a known persona (`Agent`, `Distributor`, `Internal`, `All`): treated as `Persona` (Description is empty).
  - Otherwise: treated as `Description` (Persona defaults to `All`).
- **3 Columns (Simple format)**: `Field Name \t Type \t Options` (Description is empty, Persona defaults to `All`).

## Rules & Constraints
1. **Length Limit**: Maximum 30 characters for the field name.
2. **Options Normalization**:
   - Separate options with commas (`,`).
   - Trim whitespace around options.
   - Deduplicate identical options.
3. **Description / Comment Mapping**:
   - The description column is sent directly to the platform API as `comment` (`text_field.comment` and `select_field.comment`).
   - Enables field distinction even when field titles are duplicated across departments or workflows.
4. **Role Permission & Persona Rules**:
   - Fields marked with specific personas (e.g. `Distributor`) can be automatically hidden from opposing roles (e.g. Call Center `Agent`) using the **Role Visibility Rules** panel or Role Segregation preset.
   - For non-dropdown fields (`text`, `date`) where column 3 is omitted, tab delimiters must still align properly: `Field Name \t text \t \t Description \t Persona`.
5. **Skipping / Unsupported Types**:
   - Multi-select checkboxes (`checkbox`), cascading trees (`chained_droplist`), file attachments, and rich text areas are **NOT** supported by Quick Paste.
   - Skip them and list them in the "Skipped / Unsupported Fields & Warnings" section with manual configuration guidance in Admin Console.

## Demonstration Output

```tsv
Customer Name	text		Customer full legal name	Agent
Purchase Date	date		Date of product purchase	All
Product Model	drop_list	Model Alpha, Model Beta, Model Pro	Product model code	All
Distributor Defect Code	text		Dealer internal repair defect identifier	Distributor
Issue Category	drop_list	Engine, Transmission, Electrical, Body, Other	Primary issue classification	All
Distributor Claim Status	drop_list	Pending, Approved, Rejected	Warranty claim review status	Distributor
Internal Quality Check	drop_list	Passed, Pending, Failed	Factory audit status	Internal
```
