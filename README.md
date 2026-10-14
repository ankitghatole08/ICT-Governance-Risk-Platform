
# AI-Powered ICT Governance & Risk Automation Platform

## Overview

A demonstration project for ICT governance, information security risk
management, control assessment, remediation tracking, data quality,
and AI-assisted reporting.

The project is designed around synthetic data and a human-reviewed
AI workflow. It is not a production security monitoring system.

## Technology stack

### Phase 1
- Python
- pandas
- CSV
- PowerShell
- Visual Studio Code

### Planned later phases
- Dataverse for structured governance records
- Power Apps for the governance interface
- Power Automate for notifications and approvals
- Power BI Desktop for dashboards
- Gemini API for optional AI-assisted summaries
- pytest for automated tests

Availability and licensing of Microsoft services and AI APIs will
be checked before enabling optional integrations.

## Project structure

```text
ICT-Governance-Risk-Platform/
├── data/
│   ├── raw/
│   └── processed/
├── docs/
│   └── data_model.md
├── src/
│   ├── __init__.py
│   ├── generate_data.py
│   └── validate_data.py
├── tests/
├── .gitignore
├── README.md
└── requirements.txt
```

## Setup

Python 3.11 or newer is recommended.

From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks environment activation, run this in the
current PowerShell session and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Generate synthetic data

```powershell
python -m src.generate_data
```

The generated CSV files will be written to `data/raw/`.

## Validate synthetic data

```powershell
python -m src.validate_data
```

The validator exits with a non-zero status if it finds a validation
problem.

## Data entities

- Assets
- ICT Controls
- Security Findings
- Remediation Actions

See `docs/data_model.md` for field definitions and relationships.

## Risk and AI design principles

- Use synthetic data for development and demonstrations.
- Keep deterministic risk rules separate from AI-generated text.
- Treat AI output as a draft, not an authoritative security decision.
- Require human review for recommendations and remediation decisions.
- Do not commit API keys, credentials, or confidential data.
- Verify licensing, privacy terms, and API quotas before integrating
  external services.

## Scope disclaimer

This is an educational portfolio project. Its synthetic controls,
severity distributions, remediation dates, and statuses are
illustrative. They do not represent any particular organisation's
security posture, internal controls, or policies.
