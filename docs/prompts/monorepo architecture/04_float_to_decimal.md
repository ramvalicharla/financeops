# PROMPT 04 — FIX float() IN JOURNAL BALANCE GUARD

**Sprint:** 1 (Security & Integrity)
**Audit findings closed:** #1
**Risk level:** LOW (small change, but high impact on correctness)
**Estimated effort:** XS-S (1 day including writing extra tests)

---

## CONTEXT

Repo root: `D:\finos`
Target file: `D:\finos\backend\financeops\core\intent\guards.py` (around line 237)

The audit found that the journal balance guard converts debit and credit totals through `float()` before comparing them. This is a **finance-correctness bug**, not just a precision issue:

- Floating-point comparison can return True for values that differ by fractions of a cent
- This means a journal entry can pass the "debits == credits" check while being out of balance by ₹0.0001
- Over thousands of entries, this accumulates into unreconciled balances downstream
- Fixing this *after* customer data exists is much harder — production data may already contain "balanced" entries that don't actually balance

This is a tiny code change. The work is in the regression tests.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Read the current implementation
1. Open `D:\finos\backend\financeops\core\intent\guards.py`
2. Quote the entire balance-check function (not just line 237)
3. Identify how debits and credits arrive at the guard:
   - As `Decimal`?
   - As strings that get converted?
   - As `Numeric` columns from SQLAlchemy?
4. Trace one level up the call stack — where is this guard invoked from?

### Step 2 — Search for related patterns
Run these searches and capture results:
```
rg -n "float\(" D:\finos\backend\financeops\core
rg -n "float\(" D:\finos\backend\financeops\modules\gl
rg -n "float\(" D:\finos\backend\financeops\modules\ar
rg -n "float\(" D:\finos\backend\financeops\modules\ap
rg -n "float\(" D:\finos\backend\financeops\modules\bank_recon
rg -n "float\(" D:\finos\backend\financeops\services
```

Any `float()` call on a column that represents money is a finding. List them with file:line. **Do not fix them in this prompt** — only fix the one in `guards.py`. Other findings go into a follow-up tracker.

### Step 3 — Apply the minimal fix
1. Replace `float(debits) == float(credits)` (or equivalent) with `Decimal` comparison
2. If inputs are not already `Decimal`, convert via `Decimal(str(value))` — never `Decimal(value)` for floats, never `float()` for any monetary value
3. Add a tolerance check using `Decimal('0.01')` ONLY if the existing logic explicitly allows tolerance — otherwise require exact match

### Step 4 — Add comprehensive regression tests
Create or update `D:\finos\backend\tests\test_journal_balance_guard.py`:

Test cases (all using `Decimal`):
- `test_balanced_entry_passes` — debits=Decimal("1000.00"), credits=Decimal("1000.00") → pass
- `test_unbalanced_by_one_paisa_fails` — debits=Decimal("1000.00"), credits=Decimal("999.99") → fail
- `test_unbalanced_by_subcent_fails` — debits=Decimal("1000.0001"), credits=Decimal("1000.0000") → fail (this is the bug — float would say equal)
- `test_multi_line_balanced_passes` — list of lines summing to balanced totals
- `test_multi_line_unbalanced_by_rounding_fails` — common bug: each line rounded independently
- `test_zero_value_entry_passes` — debits=0, credits=0 (valid for some entry types? confirm with code)
- `test_negative_amounts_handled` — reversing entries, contras
- `test_currency_mismatch_fails` — if the guard checks currency, ensure it raises explicitly

### Step 5 — Add a tracker entry for other float() findings
Create or append `D:\finos\docs\engineering\FLOAT_USAGE_AUDIT.md`:
- List every `float()` call found in step 2
- Classify each: `MONETARY` (must fix), `RATIO/PERCENT` (review), `NON_MONETARY` (probably OK)
- Mark this prompt's fix as `COMPLETE`
- Mark others as `OPEN` with target sprint

---

## DO NOT DO

- Do NOT fix other `float()` calls in this prompt — they get their own scoped fix
- Do NOT change the public signature of the guard function
- Do NOT change how the guard is invoked from other modules
- Do NOT modify the journal entry model
- Do NOT add a "tolerance" parameter unless the existing code already had one

---

## VERIFICATION CHECKLIST

- [ ] `guards.py` no longer calls `float()` on debit/credit totals
- [ ] All inputs are `Decimal` end-to-end through the guard
- [ ] All 8 regression tests pass
- [ ] Existing tests that exercise this guard still pass (run targeted: `pytest D:\finos\backend\tests -k balance -v`)
- [ ] `FLOAT_USAGE_AUDIT.md` lists every other `float()` finding with classification
- [ ] No new test skips, no new warnings

---

## COMMIT MESSAGE

```
fix(finance): use Decimal for journal balance guard, never float

- Replaced float() conversion with Decimal end-to-end in guards.py
- Added regression tests covering subcent imbalance, multi-line, currency
- Documented other float() findings in FLOAT_USAGE_AUDIT.md for follow-up

Closes audit finding #1 (CRITICAL).
Prevents accumulating unbalanced journal entries from floating-point drift.
```
