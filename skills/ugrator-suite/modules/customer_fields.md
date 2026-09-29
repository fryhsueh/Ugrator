# Module 2: Customer Custom Fields Specification

## Web UI Location
**Customers** > **Create Customer Fields** > Select **📋 Quick Paste from Clipboard**

## Output Format
- Code block labeled `tsv`
- Separated by literal **Tab characters (`\t`)**
- **NO header row**.

### Columns
| Column | Name | Type | Notes |
| :---: | :--- | :--- | :--- |
| **1** | Field Name | String | Max **30 characters**. Customer profile attributes. |
| **2** | Field Type | Identifier | Strictly one of: `text`, `date`, `drop_list` |
| **3** | Options | String | Comma-separated discrete options for `drop_list`. Empty for `text` and `date`. |
| **4** | Description *(Optional)* | String | Explanatory comment/description (mapped to platform API `comment`). Distinguishes identical field titles and explains usage. |

### Supported Layouts
- **4 Columns**: `Field Name \t Type \t Options \t Description`
- **3 Columns**: `Field Name \t Type \t Options` (Description defaults to empty)

## Common Automotive Customer Fields
- `VIN code` (`text`) - 17-character Vehicle Identification Number
- `Vehicle brand` (`drop_list`) - Discrete vehicle brands (e.g. `Brand Alpha, Brand Beta`)
- `State/City` (`text`) - Geographical jurisdiction or province
- `License Plate` (`text`) - Vehicle registration plate
- `Remarks` (`text`) - General customer profile notes

## Demonstration Output

```tsv
VIN code	text		17-digit Vehicle Identification Number
Vehicle brand	drop_list	Brand Alpha, Brand Beta	Authorized brand purchased by customer
State/City	text		Customer domicile state or municipality
License Plate	text		Official vehicle license plate
Preferred Contact Channel	drop_list	Phone, Email, WhatsApp	Preferred outreach channel
Customer Segment	drop_list	VIP, Fleet, Retail	Customer account classification
```
