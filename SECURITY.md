# Security Policy

## Project status & threat model

worldgen is an early-stage project. The **terrain service** (`terrain_service/`)
is an HTTP server and is the primary security surface. Today it is designed for
**single-user, local use** — it ships with **no authentication** and is intended
to be bound to `127.0.0.1`.

> ⚠️ **Do not expose the terrain service to an untrusted network** (e.g. binding
> to `0.0.0.0` on a public host) without putting it behind authentication and a
> reverse proxy with rate limiting. It performs filesystem writes and, with the
> OpenTopography provider, makes outbound API calls that consume your API quota.

## Supported versions

The project is pre-1.0 and moves fast. Security fixes are applied to `main`.
There are no long-term-support branches yet.

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for a
vulnerability.

- Preferred: open a **GitHub private security advisory**
  (repository → *Security* → *Report a vulnerability*).
- Or contact the maintainers at **[INSERT CONTACT — e.g. a project email]**.

Include: affected component, a description, reproduction steps (a request or
command), and impact. We aim to acknowledge reports promptly and will keep you
updated on remediation. Please give us reasonable time to fix before public
disclosure.

## Scope

In scope: the terrain service and tooling (`terrain_service/`, `tools/`), the
Unreal plugin's network handling, and secrets handling across the repo.

Out of scope: issues that require a malicious actor already having local
filesystem or shell access to the host running the service (that is outside the
single-user threat model), and vulnerabilities in third-party dependencies
(please report those upstream, though we welcome a heads-up).

## Hardening checklist for operators

If you run the service beyond a single local machine:

- Bind to `127.0.0.1` (the default). The CLI and demo print a warning if you
  bind elsewhere.
- **Set `WORLDGEN_API_TOKEN`** to require `Authorization: Bearer <token>` on all
  data endpoints (everything except `/health`). When unset, the service is open
  and logs a warning at startup.
- Put it behind a reverse proxy with TLS, request rate limiting, and a
  request-body-size limit.
- Keep your `OPENTOPOGRAPHY_API_KEY` in the environment, never in committed
  files (`config.json`, `demo.json`, and `.worldgen_cache/` are gitignored).
- Treat generated tile caches as untrusted if the service is shared.

## Built-in protections

- **Resource bounds** (`terrain_service/limits.py`), enforced at the HTTP
  boundary *and* defensively in the core:
  - tile `level` is constrained to `[0, 24]` (negative levels would upsample the
    sample grid into a huge allocation) and tile indices are bounded;
  - edit `radius_m`, `iterations`, and the resulting affected-tile count /
    mosaic size are capped so a single edit cannot exhaust memory or CPU;
  - `/prestage` caps the number of tiles per request.
- **Optional bearer-token auth** via `WORLDGEN_API_TOKEN` (see above).
- **Clean error mapping**: expected failures map to 4xx/5xx with non-revealing
  messages; FastAPI does not run in debug mode, so stack traces are not returned
  to clients.
- **No unsafe deserialization**: no `eval`/`exec`/`pickle`; JSON and NumPy
  `.npy` are loaded with `allow_pickle=False`.
- **Secret hygiene**: the OpenTopography API key is redacted from upstream error
  text and is not logged.

When adding endpoints or parameters, **preserve and extend these bounds** — see
[CONTRIBUTING](CONTRIBUTING.md).
