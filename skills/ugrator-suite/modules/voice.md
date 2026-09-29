# Module 6: Voice File Library Specification

## Web UI Location
**Call Center** > **Voice File Library**

The Voice File Library supports two operational modes:
1. **📁 Upload Audio Files**: Scans local audio files from disk and uploads them in batch to the platform.
2. **🗣️ Batch Text-to-Speech (TTS)**: Creates voice files directly on the platform using built-in TTS synthesis via browser automation.

---

## Mode 1: Upload Audio Files (Local Files)

### Audio Format Requirements
- **Supported Formats**: `.wav`, `.mp3`, `.ogg`, `.m4a`, `.wma`
- **Recommended Audio Standard**: 8kHz or 16kHz, 16-bit Mono PCM WAV (Standard telephony codec).

### Naming Modes in Ugrator
| Mode | Naming Pattern | Example Source File | Resulting Voice Name |
| :--- | :--- | :--- | :--- |
| `exact` | `{file_name}` | `welcome.wav` | `welcome` |
| `folder_suffix` | `{file_name}_{folder_name}` | `en/welcome.wav` | `welcome_en` |
| `prefix` | `{prefix}_{file_name}` | `welcome.wav` (prefix: `CALL_`) | `CALL_welcome` |
| `suffix` | `{file_name}_{suffix}` | `welcome.wav` (suffix: `_V1`) | `welcome_V1` |
| `custom` | Pattern string | e.g. `{prefix}_{file}_{folder}` | `CALL_welcome_en` |

---

## Mode 2: Batch Text-to-Speech (TTS) Voice Creation

Creates voice files by automating the platform's native TTS engine in the Call Center "语音列表" (Voice List) tab.

### Output & Paste Format
- Code block labeled `tsv`
- Separated by literal **Tab characters (`\t`)** or commas
- **NO header row** (headers like `Voice Name\tContent\tTimbre` are auto-skipped if present)

### Columns
| Column | Name | Type | Notes |
| :---: | :--- | :--- | :--- |
| **1** | Voice Name | String | Unique voice prompt name in tenant (e.g. `welcome_prompt`, `queue_wait`). **Enforces a strict maximum length of 20 characters** (longer names are auto-truncated to prevent validation rejection). |
| **2** | Voice Content | String | Text script to synthesize into audio. |
| **3** | Timbre / 音色 *(Optional)* | String | TTS voice persona. Defaults to `小夏` (`Little Summer`) if omitted. Bilingual mapping automatically translates Chinese timbre names to English UI equivalents (e.g., `小夏` -> `Little Summer`, `小雪` -> `Light Snow`). |

### Supported Layouts
- **2 Columns**: `Voice Name \t Voice Content` (Timbre defaults to `"小夏"` or the UI selector)
- **3 Columns**: `Voice Name \t Voice Content \t Timbre` (Row-level override for timbre)

### Automation & Execution Constraints
1. **Strict Tab Matching**: Requires the user to have already opened the **语音列表** / **Voice List** page in their debug Chrome window (`/callcenter/voice-list`).
2. **Bilingual UI Compatibility**: Fully compatible with both English and Chinese platform systems (handles English buttons `Add voice`, section label `Audio:`, input type `TTS`, and English timbre translations like `Little Summer`).
3. **Duplicate & Error Resilience**: If a voice name already exists or validation fails, the runner dismisses the modal (`Cancel` / `取消`), logs the error to the console, and continues processing the remainder of the batch.
4. **Rate Limiting**: Enforces a strict 2-second sleep between items to honor server-side TTS generation limits.
5. **Execution Control**: Can be stopped at any time via the **🛑 Stop** button.

### Demonstration Output

```tsv
welcome_prompt	Welcome to customer service. How may I assist you today?	小夏
queue_wait	All our customer representatives are currently busy. Please hold the line.	小夏
transfer_agent	Transferring your call to a customer representative. Please wait.	小夏
afterhours_notice	Our offices are currently closed. Please call back during business hours.	小夏
holiday_greeting	Thank you for calling. Our service team is currently on public holiday.	小夏
```
