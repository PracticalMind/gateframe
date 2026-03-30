# Contributing to gateframe

Thank you for your interest in contributing. This document covers how to set up a dev environment, how to add new rule types and integrations, and what the PR process looks like.

---

## Dev setup

```bash
git clone https://github.com/practicalmind-ai/gateframe.git
cd gateframe
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Lint and format:

```bash
ruff check gateframe/ tests/ examples/
ruff format --check .
ruff format .
```

All tests must pass and both checks must be clean before a PR is mergeable.

---

## Project structure

```
gateframe/
├── core/           # ValidationContract, WorkflowContext, FailureMode, EscalationRouter
├── rules/          # StructuralRule, SemanticRule, BoundaryRule, ConfidenceRule
├── integrations/   # OpenAI, Anthropic, LiteLLM, LangChain
├── audit/          # AuditLog, exporters
└── cli/            # inspect, replay subcommands
tests/              # mirrors gateframe/ structure
examples/           # runnable end-to-end examples
```

---

## How to add a new rule type

1. Create `gateframe/rules/<name>.py` with a single class inheriting from `Rule`.
2. Implement `validate(self, output, **context) -> FailureResult | None`. Return `None` on pass.
3. Catch all exceptions inside `validate` — never let them propagate. Return a `FailureResult` with the exception message instead.
4. Choose a default `failure_mode` that fits the severity: `HARD_FAIL` for scope or authority violations, `SOFT_FAIL` for confidence or quality degradation.
5. Write actionable error messages. `"Validation failed"` is not acceptable. `"Confidence 0.42 is below minimum threshold 0.7."` is.
6. Add the class to `gateframe/__init__.py` and the `__all__` list so it is part of the public API.
7. Create `tests/rules/test_<name>.py`. Cover: happy path, failure path, exception handling, custom failure mode, context forwarding, and the default name.

---

## How to add a new integration

1. Create `gateframe/integrations/<provider>.py`.
2. Add a `_require_<provider>()` guard that raises `ImportError` with install instructions if the SDK is not available.
3. Implement `extract_text`, `extract_json`, and `extract_metadata` as standalone functions (not methods). Keeping them separate from the validator class makes them individually testable.
4. Implement a `<Provider>Validator` class that accepts a `ValidationContract` and optional config, and calls the extract functions inside `validate()`.
5. Add the optional dependency to `pyproject.toml` under `[project.optional-dependencies]`.
6. Create `tests/integrations/test_<provider>.py`. Use dataclasses to mock provider responses — no real API calls. Cover all three extract functions and the validator class.

---

## Testing requirements

- Every failure path must be tested, not just the happy path.
- Use dataclasses to mock provider responses, not `unittest.mock` or real API calls.
- Tests mirror the source tree: `gateframe/rules/boundary.py` → `tests/rules/test_boundary.py`.
- Construction-time errors (e.g. `ValueError` for bad rule configuration) are tested separately from validation failures.

---

## Code style

- No `print` in library code. Use `structlog` for all internal logging.
- No unnecessary docstrings or comments. Code should be self-explanatory.
- Type hints required everywhere. `Any` requires a comment explaining why.
- One class per file where possible.
- Error messages must be actionable — include what failed, the actual value, and the expected value or constraint.
- Python 3.10+. No dependencies in core beyond `pydantic>=2` and `structlog`.

---

## PR process

1. Fork the repository and create a branch from `main`.
2. Make your changes. If you're adding a feature, add tests for it.
3. Run `python -m pytest tests/ -v` — all tests must pass.
4. Run `ruff check gateframe/ tests/ examples/` and `ruff format --check .` — both must be clean.
5. Open a pull request with a description of what the change does and why.

If you're unsure whether a change fits the scope of the project, open an issue first.
