# Onboarding Wizard

**[Try it →](https://onboarding-wizard-mk6m.onrender.com/)** — this repo's own live deployment.

A self-service setup wizard: a visitor walks through it, in their own
browser, to provision their own instance of a separate PR-review bot —
creating and validating a GitHub App, provisioning a Supabase project,
supplying an LLM provider credential, setting up an UptimeRobot keep-warm
monitor, and triggering the final Render deploy — ending with their own
live bot+dashboard service.

Every credential in that flow is the *visitor's own*: this service relays
each one to the relevant external API to validate/act on it, and never
holds a long-lived operator credential of its own. See `CLAUDE.md` for the
full architecture, per-frame design notes, and the secret-handling rules
that govern this codebase.

## Local development

```bash
uv sync --all-extras --dev
cp .env.example .env
```

Fill in `.env`'s two required settings:

- `DATABASE_URL` — this service's own dedicated Postgres, used only for its
  server-side wizard session (never a visitor's provisioned project).
- `ONBOARDING_SESSION_ENCRYPTION_KEY` — a Fernet key used to encrypt every
  credential value before it's written to that session store. Generate one
  with:

  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

Then run:

```bash
uv run pytest -v
uv run ruff check .
```

## Deployment

Deployed on Render as a single Docker web service (`render.yaml`,
`Dockerfile`), backed by its own dedicated Supabase/Postgres session store
(`DATABASE_URL` above) — never the bot's own database. Live at
<https://onboarding-wizard-mk6m.onrender.com/>. See
`docs/superpowers/specs/2026-09-01-onboarding-server-side-session-design.md`
for the full session design.

## Related project

This wizard provisions deployments of a separate PR-review bot+dashboard
project, which lives in its own repository — not part of this codebase.

## More

- `CLAUDE.md` — full architecture, module contracts, and secret-handling
  rules.
- `ISSUES.md` — this service's incident and parked-issue history.
