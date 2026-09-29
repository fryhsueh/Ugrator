# Module 7: Ticket Templates Creation Specification

## Web UI Location
**Tickets** > **Create Ticket Templates**

---

## Output Format
- Code block labeled `tsv` or text
- **Hierarchical Block Structure**: Each template begins with a header line (`Template: <Name>`), followed by its associated field rows.
- Multiple templates can be defined in a single block separated by blank lines.

### Structure & Syntax
```tsv
Template: <Template Name>
<Field Identifier 1>	<Required Flag>
<Field Identifier 2>	<Required Flag>
...

Template: <Next Template Name>
<Field Identifier 3>	<Required Flag>
```

### Accepted Header Formats
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
   - If **any** referenced field or ID does not exist in the tenant, template creation is **strictly blocked**.
   - The UI displays an alert specifying which template is missing which fields.
   - You must first create the missing fields in **Tickets** > **Create Custom Fields** before creating the template.

---

## Demonstration Output

```tsv
Template: Vehicle Complaint Ticket
VIN (#28101)	true
Car Model (field_28102)	false
Dealer Code*
#28104	optional
Purchase Date
Complaint Description	true

Template: Periodic Maintenance Ticket
Plate Number	required
Current Mileage	true
Service Advisor	false
Maintenance Type*
Next Service Due Date
```
