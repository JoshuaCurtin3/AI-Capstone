# Phishing risk-scoring rules

Every rule implemented in `app/phishing_detection/rules/` must be documented
here and have a corresponding test in `tests/unit/`. A feature is not
considered complete until its tests pass (see CLAUDE.md).

## Rule template

Copy this block for each new rule:

```
### <rule_id> — <short name>

- **File**: app/phishing_detection/rules/<file>.py
- **Test**: tests/unit/<test file>
- **Signal**: what pattern/condition this rule detects
- **Score contribution**: how much this rule adds to the total score, and why
- **Determinism note**: confirm the rule has no external/network/LLM dependency
```

No rules are implemented yet.
