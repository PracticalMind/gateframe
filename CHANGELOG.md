# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `ContractTrendAnalyzer` for detecting per-contract pass-rate regressions across workflow runs
- `gateframe trend` CLI subcommand for running trend analysis on an audit log
- `WorkflowContext.reset()` for reusing a context across independent workflow runs

## [0.2.0] - 2026-03-30

### Added
- `WorkflowContext` — carries validation state and cumulative confidence across multi-step workflows
- `EscalationRouter` — routes threshold breaches to human review, abort, or custom handlers
- `SemanticRule` — validates behavioral constraints via arbitrary callables
- `BoundaryRule` with `AllowedValues` check — enforces decision boundaries on field values
- `ConfidenceRule` — flags outputs below a minimum confidence threshold
- Provider integrations: OpenAI, Anthropic, LiteLLM, LangChain
- `AuditLog` with `JsonFileExporter` and `OtlpExporter`
- CLI: `gateframe inspect` and `gateframe replay`
- Top-level public API via `gateframe.__init__`
- End-to-end examples: `triage_workflow`, `rag_output`, `agent_pipeline`

## [0.1.0] - 2026-03-27

### Added
- `Rule` base class with abstract `validate` interface
- `StructuralRule` — validates output structure against a Pydantic model
- `ValidationContract` — composes multiple rules, returns structured `ValidationResult`
- `FailureMode` enum: `HARD_FAIL`, `SOFT_FAIL`, `RETRY`, `SILENT_FAIL`
- Structured audit logging for validation events
- GitHub Actions CI with ruff lint and pytest matrix (Python 3.10–3.13)

[Unreleased]: https://github.com/PracticalMind/gateframe/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/PracticalMind/gateframe/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/PracticalMind/gateframe/releases/tag/v0.1.0