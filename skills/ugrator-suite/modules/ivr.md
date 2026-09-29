# Module 5: IVR Canvas Flow Builder Specification

## Web UI Location
**Call Center** > **IVR Flow Builder** > Paste YAML into editor or load file

## Output Format
- Valid, lint-free YAML block (`yaml`)
- Structure:
  - `name`: Flow name string
  - `description`: Overview string
  - `default_voice`: Global fallback audio file name
  - `nodes`: List of canvas node definitions

## Supported Node Types

| Node Type | Purpose | Key Attributes |
| :--- | :--- | :--- |
| `menu` | Multi-digit branch menu | `prompt_voice`, `timeout_seconds`, `max_retries`, `branches` (key: '1', '2', etc.), `timeout_target`, `invalid_target` |
| `play_voice` | Plays an announcement audio | `voice_file`, `next_node` |
| `transfer_group` | Transfers call to agent group | `group_name` |
| `info_judgment` | Branch based on customer attributes (e.g. VIP, region) | `rules` (field, operator, value, target), `default_target` |
| `time_judgment` | Branch based on working hours | `schedule`, `in_hours_target`, `out_of_hours_target` |
| `jump` | Cross-canvas or intra-canvas link | `target_node` |

## Demonstration Output

```yaml
name: "Global_Customer_Service_IVR"
description: "Production IVR flow for customer service and emergency rescue"
default_voice: "welcome_prompt.wav"

nodes:
  - id: "root_menu"
    type: "menu"
    name: "Main Language Menu"
    prompt_voice: "main_menu_voice.wav"
    timeout_seconds: 5
    max_retries: 3
    branches:
      - key: "1"
        target: "inquiry_menu"
      - key: "2"
        target: "complaint_queue"
      - key: "3"
        target: "roadside_emergency"
    timeout_target: "transfer_general"
    invalid_target: "transfer_general"

  - id: "inquiry_menu"
    type: "transfer_group"
    name: "Inquiry Agent Group"
    group_name: "Customer Inquiry Group"

  - id: "complaint_queue"
    type: "transfer_group"
    name: "Complaint Team"
    group_name: "Complaint & Quality Group"

  - id: "roadside_emergency"
    type: "transfer_group"
    name: "24/7 Rescue Dispatch"
    group_name: "Roadside Assistance Unit"

  - id: "transfer_general"
    type: "transfer_group"
    name: "General Operator Queue"
    group_name: "Default Agent Group"
```
