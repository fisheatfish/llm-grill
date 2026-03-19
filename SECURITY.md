# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT open a public issue.**
2. Email the maintainers or use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability).
3. Include a description, steps to reproduce, and potential impact.

We will acknowledge receipt within 48 hours and aim to provide a fix within 7 days for critical issues.

## Scope

The following are in scope:

- API key exposure through scenario files, logs, or JSONL output
- SSH credential leaks (GPU monitoring feature)
- Command injection via scenario YAML parsing
- Dependency vulnerabilities

## Best Practices for Users

- **Use `${ENV_VAR}` syntax** for API keys in scenario files — never hardcode them
- **Rotate keys** regularly and set expiration dates
- **Use fine-grained tokens** with minimal permissions
- **Do not commit** `.env` files or `*.jsonl` results containing sensitive data
- **Restrict SSH keys** used for GPU monitoring to read-only operations
