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

- Bind to `127.0.0.1` (the default) or put it behind an authenticating proxy.
- Add request rate limiting and request-size limits at the proxy.
- Keep your `OPENTOPOGRAPHY_API_KEY` in the environment, never in committed
  files (`config.json`, `demo.json`, and `.worldgen_cache/` are gitignored).
- Treat generated tile caches as untrusted if the service is shared.

## Good security practices in the codebase

- The core is deterministic and free of `eval`/`exec`/`pickle`; JSON and NumPy
  `.npy` are loaded without pickle (`allow_pickle=False` by default).
- Input validation and resource bounds on request parameters are enforced in the
  service layer (see `terrain_service/service.py`); please preserve and extend
  these when adding endpoints. See [CONTRIBUTING](CONTRIBUTING.md).
