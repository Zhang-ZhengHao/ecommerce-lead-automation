# E-commerce Lead Automation

[![Verify](https://github.com/Zhang-ZhengHao/ecommerce-lead-automation/actions/workflows/verify.yml/badge.svg?branch=main)](https://github.com/Zhang-ZhengHao/ecommerce-lead-automation/actions/workflows/verify.yml)
[![Release](https://img.shields.io/github/v/release/Zhang-ZhengHao/ecommerce-lead-automation?display_name=tag&sort=semver)](https://github.com/Zhang-ZhengHao/ecommerce-lead-automation/releases/latest)

**English** | [简体中文](README.zh-CN.md)

Turn a redacted customer-message spreadsheet into a reviewable lead queue. This Streamlit application classifies messages, drafts replies and follow-up actions, lets a person edit and confirm final text, and exports auditable workbooks.

The default demo is deterministic and runs without an API key. An OpenAI-compatible endpoint is optional and remains disabled until both an explicit feature flag and a key are configured.

![Processed lead queue](screenshots/result.png)

## Engineering evidence

- The unit and regression suite covers classification, spreadsheet import and
  export, human confirmation, sendable-row isolation, usage limits, and the
  synthetic golden fixture.
- [GitHub Actions](https://github.com/Zhang-ZhengHao/ecommerce-lead-automation/actions/workflows/verify.yml)
  verifies Python 3.10 and 3.12, compiles the Python sources, and checks the
  installed dependency graph.
- The golden workbook records expectation provenance and deliberately excludes
  unverified examples from classification-accuracy assertions.
- The runtime footer exposes both the semantic application version and the
  process-captured build SHA, making stale deployments visible.
- The default workflow remains offline and requires explicit human confirmation
  before a row can enter the separately generated sendable workbook.

## Features

- Imports `.xlsx` and `.csv` files, including CSV input in common UTF-8 and GB18030-family encodings.
- Detects likely message columns while preserving source columns and avoiding name collisions with generated fields.
- Classifies intent and customer type, produces a reply draft and follow-up action, and isolates a failed row instead of stopping the batch.
- Includes offline rules plus presets for e-commerce enquiries, after-sales support, and B2B quotations.
- Tracks `New`, `Contacted`, `Needs information`, and `Handed off` funnel states for the current browser session.
- Keeps AI drafts separate from final replies. A row enters the sendable export only after explicit human confirmation and a second safety check.
- Exports complete, high-intent, and needs-review worksheets, plus a separate sendable workbook.
- Escapes formula-like spreadsheet cells and validates reply length, enums, commitment categories, and configurable forbidden terms.
- Includes a synthetic 15-row regression workbook with provenance metadata; unverified examples are excluded from classification assertions.

## Technology

- Python 3.10+
- Streamlit 1.64
- pandas 2.2.3
- openpyxl 3.1.5
- pytest 9.0.3+ for the test suite

The optional model client uses Python's standard-library HTTP client against an OpenAI-compatible chat-completions endpoint.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PORT=8501 bash start.sh
```

Open `http://localhost:8501`, choose **载入示例数据** (load sample data), and run the offline demo. The bundled contacts and messages are synthetic.

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

### Optional model endpoint

Copy the variable names from `.env.example` into your deployment environment or secret manager. Do not put a real key in a file committed to Git.

```bash
export COMMERCE_LEAD_ENABLE_REAL_AI=true
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional
export OPENAI_MODEL="gpt-4o-mini"                    # optional
PORT=8501 bash start.sh
```

When enabled, this mode sends customer-message text to the configured provider and may incur provider charges. The application limits it to 200 rows per file and 200 rows per browser session.

## Review and export flow

1. Upload a redacted spreadsheet or load the synthetic example.
2. Confirm the detected message column and choose an industry preset or custom reply profile.
3. Process with offline rules, or deliberately select the configured model endpoint.
4. Filter the queue, inspect a draft, and update its session-only funnel stage.
5. Copy the draft into the final-reply editor, revise it, and confirm it. Unsafe text is routed back to review.
6. Download the full draft workbook, the needs-review workbook, or the strictly filtered sendable workbook.

An imported file is limited to 10 MB and 5,000 rows. Model requests accept at most 4,000 characters from one message and validate returned reply fields at 2,000 characters.

## Tests

Install the development requirements, then run the same checks used by CI:

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=. python -m pytest -q tests
python -m compileall -q app.py services tests
python -m pip check
```

The GitHub Actions workflow runs these checks on Python 3.10 and 3.12. For the spreadsheet regression fixture alone, run:

```bash
PYTHONPATH=. python -m pytest -q tests/test_golden_fixture.py
```

## Security and data boundaries

- Demo mode does not call an external model. Uploaded tables and reply settings are held in the current Streamlit session; this repository contains no customer database or task-history store.
- Model mode sends message content to the configured endpoint. Remove names, phone numbers, order details, credentials, payment data, and other unnecessary personal information before upload.
- `OPENAI_BASE_URL` must be a credential-free HTTP(S) URL without a query or fragment. Use HTTPS outside a trusted local environment; URL validation does not make an arbitrary third-party endpoint trustworthy.
- Keep `OPENAI_API_KEY` in environment-based secret storage. `.env` files, private-data directories, customer-data directories, exports, and Streamlit secrets are ignored by Git.
- Generated replies are drafts, not approved customer communications. The sendable label requires a person to save and confirm a final reply, followed by an export-time policy check.
- Workbook exports escape cells beginning with `=`, `+`, `-`, or `@` to reduce formula-injection risk.

See [SECURITY.md](SECURITY.md) for safe-use and private-reporting guidance. The initial label and forbidden-term policy is documented in [POLICY_DEFAULTS.md](POLICY_DEFAULTS.md).

## Production boundaries

This repository is a demonstrable workflow, not a production messaging platform. It does not provide user accounts, authentication, role-based access, durable storage, audit logs, background jobs, or direct integration with a marketplace messaging API. It does not automatically send replies, log in to a shop, bypass platform controls, or promise classification accuracy, conversion results, inventory, price, delivery, or after-sales outcomes.

Before production use, add access control, encrypted and durable storage where required, retention and deletion rules, auditability, monitoring, backups, rate limits, provider-specific privacy review, and deployment-specific acceptance tests. Calibrate labels and forbidden terms with customer-approved, redacted examples, and keep a human reviewer responsible for every outbound message.

## Repository layout

```text
app.py                    Streamlit interface and session workflow
services/                 import, classification, review, export, and model modules
examples/demo.csv         synthetic demonstration input
tests/                    unit and regression tests
tests/fixtures/           synthetic golden workbook and provenance metadata
.github/workflows/        Python 3.10/3.12 verification
```

## License

Released under the [MIT License](LICENSE). Release history is recorded in the
[changelog](CHANGELOG.md), and third-party dependency notices are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
