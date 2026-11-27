# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.0-rc.1 | ✅ Active |
| 0.1.x | ⚠️ Best-effort only (no backports) |

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in this project, please **do not open a public GitHub issue**.

Instead, report it privately via one of these channels:

1. **GitHub Security Advisories** (preferred): [Report a vulnerability](https://github.com/Stacey77/agi-system/security/advisories/new)
2. **Email**: Contact the repository owner through their GitHub profile.

### What to include

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code or curl commands are helpful)
- Affected version(s)
- Any suggested mitigations you are aware of

### Response timeline

| Stage | Target |
|---|---|
| Acknowledgement | Within 5 business days |
| Initial assessment | Within 10 business days |
| Fix / advisory | Within 90 days (critical: sooner) |

We follow [responsible disclosure](https://cheatsheetseries.owasp.org/cheatsheets/Vulnerability_Disclosure_Cheat_Sheet.html): once a fix is available we will publish a GitHub Security Advisory crediting the reporter (unless they prefer to remain anonymous).

## Security Hardening Notes

Before deploying to production, ensure the following are configured:

- **`JWT_SECRET`** — Set to a stable 64-character hex value (`openssl rand -hex 32`). If unset, an ephemeral secret is generated per restart, invalidating all tokens.
- **`API_KEYS`** — Configure at least one API key. Without this, all endpoints are publicly accessible.
- **`CORS_ORIGINS`** — Set to a specific comma-separated list of allowed origins. The default `http://localhost:8000` must be changed for any public deployment.
- **`LOG_LEVEL`** — Use `INFO` or higher in production. `DEBUG` may log sensitive request data.

See `.env.example` for full configuration documentation.
