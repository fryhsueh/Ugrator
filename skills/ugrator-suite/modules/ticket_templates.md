# Module 7: Ticket Templates Creation & Update Specification

## Web UI Location
**Tickets** > **Create Ticket Templates**

---

## Capabilities & Workflows

Ugrator supports three primary operations for Ticket Templates:
1. **Batch Template Creation**: Creates brand new templates via `POST /cs/ts/api/ticket_templates`.
2. **Live Templates Fetching**: Pulls all existing live templates from the tenant (`GET /cs/ts/api/ticket_templates`) via the **📋 Fetch & Copy Live Templates (TSV)** button, formatting them into editable TSV and copying directly to your clipboard.
3. **Batch Template Update (Full Overwrite)**: Modifies existing templates via `PUT /cs/ts/api/ticket_templates/{id}` via the **🔄 Update Existing Templates** button.

---

## Output Format
- Code block labeled `tsv` or text
- **Hierarchical Block Structure**: Each template begins with a header line (`Template: <Name>`), followed by its associated field rows.
- Multiple templates can be defined in a single block separated by blank lines.

### Structure & Syntax
```tsv
Template: <Template Name> (#<Optional Template ID>)
<Field Identifier 1>	<Required Flag>
<Field Identifier 2>	<Required Flag>
...

Template: <Next Template Name> (#<Optional Template ID>)
<Field Identifier 3>	<Required Flag>
```

### Accepted Header Formats
- `Template: <Name> (#<ID>)` (e.g. `Template: Complaint Ticket (#1024)`)
- `Template: <Name>` (e.g. `Template: Complaint Ticket`)
- `Ticket Template: <Name>`
- `模板：<名称>` or `模板: <名称>`
- `[<Name>]`
- Markdown headings: `## <Name>`

### Field Row Columns
| Column | Name | Type | Notes |
| :---: | :--- | :--- | :--- |
| **1** | Field Identifier | String | Name, numeric ID, or field code of the ticket field. Strips leading bullet marks (`- `, `* `, `1. `). |
| **2** | Required Flag *(Optional)* | String / Boolean | Marks whether the field is mandatory in this template. Defaults to `false` (optional) if omitted. |

---

## Supported Field Identifier Formats & Duplicate Handling

In the platform, multiple custom fields may share identical titles (e.g., duplicate `VIN` or `Fault Description` fields created across iterations). To ensure exact matching and resolve duplicates, the Migrator supports all of the following identifier formats:

1. **Title with Embedded ID** *(Recommended for clarity)*:
   - `VIN (#28101)`
   - `VIN (ID: 28101)` or `VIN (id: 28101)`
   - `VIN [28101]`
   - `VIN #28101`
   - `VIN (field_28101)`
2. **Pure Numeric ID**:
   - `#28101`
   - `28101`
3. **Field Code**:
   - `field_28101`
4. **Standard Field Title**:
   - `VIN`
   - `Product Model`

> [!NOTE]
> If a plain title is supplied and multiple fields share that title in the platform, the Migrator binds to the first field and displays a duplicate warning highlighting candidate IDs so you can disambiguate using `Title (#ID)`.

#### Accepted Values for Required:
- **Mandatory / Required**: `true`, `1`, `yes`, `required`, `必填`, or prefix/suffix asterisk (`*VIN` or `VIN*`) or inline label `(required)` / `（必填）`.
- **Optional**: `false`, `0`, `no`, `optional`, `选填`, or omitting column 2.

---

## Strict Guard Validation Rule
1. **Pre-flight Integrity Check**:
   - The Migrator cross-references every field identifier in the pasted block against the tenant's live ticket fields (fetched from `/cs/ts/api/ticket_fields`).
2. **Strict Block on Missing Fields**:
   - If **any** referenced field or ID does not exist in the tenant, both template creation and update are **strictly blocked**.
   - The UI displays an alert specifying which template is missing which fields.
   - You must first create the missing fields in **Tickets** > **Create Custom Fields** before proceeding.

---

## Template Update Matching & Strategy

When updating existing templates (**🔄 Update Existing Templates**):
1. **Target ID Resolution**:
   - The Migrator inspects the header for an embedded `#<ID>` (e.g. `Template: Vehicle Complaint (#1001)`).
   - If no `#<ID>` is found, it matches against live tenant templates by exact case-insensitive name.
   - If the template cannot be located in the tenant, it is reported as an error (use "Create Ticket Templates" for new templates).
2. **Full Overwrite Strategy**:
   - The template's active fields list is completely replaced by the exact mapped fields defined in the TSV block.
   - Existing template attributes (scope, permissions, rules, default status) are safely preserved.
3. **Rate Limiting**:
   - Sequential requests enforce a 2-second delay between templates to maintain stability.

---

## Demonstration Output

```tsv
Template: Vehicle Complaint Ticket (#1001)
VIN (#28101)	true
Car Model (field_28102)	false
Dealer Code*
#28104	optional
Purchase Date
Complaint Description	true

Template: Periodic Maintenance Ticket (#1002)
Plate Number	required
Current Mileage	true
Service Advisor	false
Maintenance Type*
Next Service Due Date
```
