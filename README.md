# Ugrator

[![Tests](https://img.shields.io/badge/tests-98%20passing-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

**Ugrator** is an enterprise-grade automation toolkit and Web UI for accelerating customer onboarding, tenant migration, and configuration management across cloud Contact Center, IM, Ticket, and ServiceGo environments.

---

## Key Features

### 1. Custom Fields Creator (Ticket & Customer)
- **Visual Grid & Quick Paste**: Paste fields directly from Excel, Google Sheets, or TSV/CSV.
- **Persona & Visibility Controls**: Automatically configure agent, customer, and partner persona permissions (e.g. Distributor vs. Internal Agent).
- **Safe Streaming Ingestion**: Real-time server-sent event (SSE) streaming execution with automated rate-limiting to prevent tenant throttling.

### 2. Ticket Template Management & Migration
- **Cross-Tenant Migration**: Automatically identifies field schema differences between source and target tenants, maps field IDs, and reconstructs template structures.
- **Template Creator**: Define ticket templates with hierarchical layout blocks and bind fields using field titles, custom codes, or explicit field IDs.
- **Strict Guard Validation**: Pre-validates payloads and field compatibility before dispatching requests.

### 3. Agent & Group Automation
- **Batch Agent Provisioning**: Create agents in bulk with default roles, departments, user groups, and credentials.
- **Automated Group Assignment**: Map agents to multiple routing groups via CSV mapping.

### 4. Call Center Voice Library & Batch TTS
- **Directory Audio Uploader**: Scan local voice prompt directories with configurable naming rules (exact, prefix, suffix, folder tags).
- **Batch Text-to-Speech (TTS) Engine**: Automate the platform's native TTS synthesis engine via Chrome DevTools Protocol (CDP) with multi-timbre support.

### 5. IVR Flow Builder
- **Declarative YAML Workflows**: Define multi-branch, multi-level IVR call flows in clean, human-readable YAML.
- **DAG Layout Compiler**: Automatically computes collision-free 2D canvas coordinates for tree and branching structures.
- **Browser Automation**: Programmatically draws and connects nodes directly on the cloud IVR canvas.

---

## Quick Start

### Prerequisites
- Python 3.8+
- Modern Web Browser (Google Chrome recommended)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/ugrator.git
   cd ugrator
   ```
2. Install Python dependencies:
   ```bash
   pip install requests pyyaml pandas openpyxl websockets
   ```

### Running the Application
Launch the local web server and open the interface:
- **Windows**: Double-click `start_migrator.bat` or run:
  ```bash
  python server.py
  ```
- Open [http://localhost:8081](http://localhost:8081) in your browser.

---

## Browser Automation Setup (IVR & Voice Library)

For browser-driven features (Batch TTS and IVR Canvas Drawing):
1. Launch Chrome with remote debugging enabled:
   - Run `start_debug_chrome.bat` or start Chrome from the command line:
     ```bash
     chrome.exe --remote-debugging-port=9225 --user-data-dir="C:\ChromeDebug_Ugrator"
     ```
2. Log in to your tenant in this debug browser window.
3. Open the target page (e.g., **Voice List** `/callcenter/voice-list` or **IVR Editor** `/callcenter/ivr/flow-process`).
4. Execute actions directly from the Ugrator web console.

---

## Automated Test Suite

Ugrator includes a comprehensive test suite covering API request translation, cookie parsing, coordinate layout mathematics, and input sanitation:

```bash
# Run all unit tests
python -m unittest discover tests

# Run a specific module
python -m unittest tests.test_ivr
python -m unittest tests.test_fields
```

---

## Directory Structure

```text
Ugrator/
├── core/                   # Backend engines (auth, fields, templates, voice, ivr, agents)
├── frontend/               # Single-page Web UI application (Vanilla HTML/CSS/JS)
├── skills/                 # Agentic workflow guides and documentation
│   └── ugrator-suite/
├── tests/                  # Automated unit test suite
├── workflows/              # Sample declarative IVR workflow definitions
├── server.py               # Lightweight Python HTTP server and API router
├── start_migrator.bat      # Quick launcher script
└── README.md
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
