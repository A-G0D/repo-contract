# Summary

<!-- What does this change do, and why? Link the issue if there is one. -->

## Type of change

- [ ] Bug fix
- [ ] New extraction rule or policy category
- [ ] Documentation
- [ ] Refactor (no behavior change)

## Verification

```bash
# paste the commands you ran and their results
ruff check .
ruff format --check .
python3 -m pytest -q
python3 demo/run_demo.py
```

## Classification changes (if any)

<!-- If this changes policy classification, show the input snippet and the old/new category. -->
- Input:
- Before:
- After:

- [ ] Ambiguous/positive cases covered by tests.
- [ ] No network access, no writes to the target repository.

## AI assistance

<!-- Keep one line if applicable: -->
AI assistance: prepared with an AI coding agent; I reviewed and ran the checks above.
