# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.2.x   | Yes       |
| < 0.2   | No        |

## Reporting a vulnerability

Use [GitHub's private vulnerability reporting](https://github.com/PracticalMind/gateframe/security/advisories/new) to submit a report. Do not open a public issue.

Include a description of the issue, steps to reproduce, and the version affected. You will receive a response within 7 days.

## Scope

gateframe is a library, not a network service. The relevant attack surface is:

- **Audit log parsing** — `ContractTrendAnalyzer` and `gateframe replay` read JSONL files from disk. Malformed or adversarially crafted audit files could affect behavior.
- **SemanticRule callables** — `SemanticRule` accepts arbitrary Python callables. This is by design; callers are responsible for the code they pass in.
- **Provider integrations** — gateframe does not handle API keys or credentials. Credential security is the responsibility of the LLM SDK in use (openai, anthropic, etc.).
- **Dependency vulnerabilities** — if you find a vulnerability in a dependency (pydantic, structlog, opentelemetry), report it upstream and open an issue here so we can update the pin.