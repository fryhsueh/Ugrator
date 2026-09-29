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

| Node Type | UI Label (Auto-detected across tenants) | Purpose | Key Attributes |
| :--- | :--- | :--- | :--- |
| `start` | `Start node` / `Start` / `开始` | Entry point of canvas | `id`, `routes` (`default`) |
| `play_prompt` / `voice_playback` / `play_voice` | `Play prompt` / `Voice playback` / `放音` | Plays prompt audio or greeting announcement | `audio`, `routes` (`default`) |
| `collect_input` | `Collect input` / `按键收号` | DTMF digit collection menu | `audio`, `config` (`timeout_seconds`, `max_retries`), `routes` (`keys`, `timeout`, `invalid`) |
| `enter_queue` | `Enter Queue` / `转人工` | Routes call to agent group queue | `config` (`group_name`), `routes` (`default`) |
| `info_judgment` | `information judgment` / `信息判断` | Conditional branching based on customer/IVR attributes | `rules` (`name`, `variable`, `operator`, `value`, `target`), `routes` (`default`) |
| `hang_up` | `Play prompt` / `Voice playback` / `放音` (end call action) | Terminates call session | `audio`, `routes` |
| `transfer_external` | `Transfer to external number` / `Transfer to outside line` / `转外线` | Transfers call to PSTN / external number | `config` (`phone_number`), `routes` (`default`) |
| `speech_recognition` | `Speech Recognition` / `语音识别` | ASR speech recognition branch | `config`, `routes` |
| `voice_message` | `Voice Message` / `语音留言` | Voicemail recording | `config`, `routes` |

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
