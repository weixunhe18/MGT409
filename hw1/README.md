# HW 1 — AI Financial Document Analysis

This folder contains the scripts and outputs for Homework 1. The scripts use the OpenAI-compatible Portkey endpoint and the model `gpt-5.6-luna`, as required by the project `AGENTS.md` instructions.

## Install

From the repository root:

```bash
cd hw1
python3 -m venv .venv
source .venv/bin/activate
pip install openai python-dotenv pypdf
```

## Environment variables

Create a local `.env` file at the repository root, one level above this folder:

```text
PORTKEY_API_KEY=your_portkey_api_key_here
```

Keep the real key out of source files, `README.md`, logs, and the ZIP submission. The scripts read this variable from the root `.env` file and send model requests through:

```text
https://api.portkey.ai/v1
```

The model is:

```text
gpt-5.6-luna
```

## Run the scripts

Run these commands from the `hw1` folder with the virtual environment activated. The unzipped document pack is `hw1_spoke_and_wrench`.

```bash
python read_receipts.py --docs-dir hw1_spoke_and_wrench --out-dir output
python read_bank.py --docs-dir hw1_spoke_and_wrench --out-dir output
python read_card.py --docs-dir hw1_spoke_and_wrench --out-dir output
python reconcile.py --docs-dir hw1_spoke_and_wrench --out-dir output
python income_statement.py --docs-dir hw1_spoke_and_wrench --out-dir output
python report.py --docs-dir hw1_spoke_and_wrench --out-dir output
```

The scripts produce these main files in `output/`:

- `receipts.json`
- `bank_transactions.json`
- `credit_card_transactions.json`
- `reconciliation_log.json`
- `income_statement_jan2026.json`
- `income_statement.html`

`output/judgment_calls.json` is the judgment-call JSON array used by the report. `output/pipeline.html` is a static process diagram and does not require a Python command.

## Prompt files

Runtime prompts are stored separately in `prompts/`:

- `receipts_extract.md`
- `bank_extract.md`
- `card_extract.md`
- `reconcile.md`
