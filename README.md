# Supabase for Kiro Crew

A Kiro Crew app that brings the [Supabase Hosted Kiro Power](https://github.com/supabase-community/kiro-powers/tree/main/powers/supabase-hosted) to Kiro Crew.

It adds:

- The hosted Supabase MCP server (`https://mcp.supabase.com/mcp`), registered as `@supabase:supabase`.
- A `supabase` agent for Supabase development work.
- A `supabase-hosted` skill with the Power's guides for the Supabase CLI, the database workflow, onboarding, SQL style, migrations, declarative schema, RLS policies, Postgres functions, Edge Functions, Next.js auth and Realtime.

## Install

### From the dashboard (no clone)

1. Go to Apps, then Discover, then Manage app sources.
2. Add `https://github.com/nadetastic/supabase-crew-app` as a source.
3. Find Supabase in Discover and select Install.

### From the command line

```bash
git clone https://github.com/nadetastic/supabase-crew-app.git
kirocrew app install ./supabase-crew-app
kirocrew app enable supabase
```

You can also install it from the dashboard: Apps, then the Sources gear, then install from a local path.

The first call to a Supabase MCP tool opens a Supabase sign-in in your browser.

## Use

Pick the `supabase` agent in the agent picker, or ask any agent about Supabase work and it will load the `supabase-hosted` skill.

To scope the MCP server to one project or make it read-only, edit the `url` in `app.json`, for example:

```
https://mcp.supabase.com/mcp?project_ref=<your-project-ref>&read_only=true
```

Then reinstall the app.

## Differences from the Power

- Power steering files live in `skills/supabase-hosted/references/`.
- Kiro IDE hooks (`supabase-hooks.md`) do not apply in Kiro Crew. The skill offers to run the same checks as cron jobs instead.

## Structure

```
supabase-crew-app/
├── app.json
├── agents/
│   └── supabase.json
├── assets/
│   └── icon.png
├── skills/
│   └── supabase-hosted/
│       ├── SKILL.md
│       └── references/
├── LICENSE
└── README.md
```

## License

MIT. The guides in `skills/supabase-hosted/references/` come from [supabase-community/kiro-powers](https://github.com/supabase-community/kiro-powers), Copyright (c) 2025 Supabase. See `LICENSE`.
