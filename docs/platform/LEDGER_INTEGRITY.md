# Ledger Integrity

`docs/ledgers/PROMPTS_LEDGER.md` now uses a tamper-evident hash chain for prompt execution rows.

## Status Row Hash Fields

Each status row includes:

- `prev_hash`
- `entry_hash`

Where:

- `prev_hash` is previous row's `entry_hash` (or `GENESIS` for first row)
- `entry_hash = sha256(prompt_id + "|" + status + "|" + timestamp + "|" + prev_hash)`

## Verification

Run:

```bash
python -m financeops.prompt_engine.cli ledger verify
```

Engine startup also verifies integrity. If broken, execution fails closed by default.

## Repair

Deterministic repair command:

```bash
python -m financeops.prompt_engine.cli ledger repair --yes
```

Repair behavior:

- preserves existing prompt/status/timestamp values
- recomputes `prev_hash` and `entry_hash` in row order
- does not alter execution statuses

To allow automatic startup repair for one run:

```bash
python -m financeops.prompt_engine.cli run --allow-ledger-repair
```
