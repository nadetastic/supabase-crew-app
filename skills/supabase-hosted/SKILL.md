---
name: supabase-hosted
description: Build fullstack applications with hosted Supabase (Postgres database, authentication, storage, real-time subscriptions) through the Supabase CLI and the hosted Supabase MCP server. Use for Supabase setup, SQL, migrations, declarative schema, RLS policies, Postgres functions, Edge Functions, Next.js auth with Supabase SSR, and Realtime.
always: false
triggers: supabase, supabase project, supabase mcp, postgres rls, row level security, supabase migration, edge function, supabase auth, supabase realtime
---

# Supabase Hosted Development

The reference files live in the `references/` folder next to this file.

## When to read reference files

You MAY read multiple reference files if multiple topics are relevant.
You must ALWAYS read `references/supabase-cli.md` to understand how to invoke Supabase CLI.
You must ALWAYS read `references/supabase-hosted-database-workflow.md` to understand how to interact with the database through CLI and MCP.
**IMPORTANT** You CANNOT perform actions (MCP tools, reading/writing files) before reading relevant reference file(s).

In addition, consider these cases to read other reference files:

- First time setup and troubleshooting Supabase project configuration → `references/supabase-hosted-onboarding.md`
- Writing or formatting SQL code → `references/supabase-prompts-code-format-sql.md`
- Writing Supabase Edge Functions (TypeScript/Deno) → `references/supabase-prompts-edge-functions.md`
- Creating or modifying RLS policies → `references/supabase-prompts-database-rls-policies.md`
- Creating PostgreSQL functions → `references/supabase-prompts-database-functions.md`
- Setting up or modifying Next.js authentication with Supabase SSR → `references/supabase-prompts-nextjs-supabase-auth.md`
- Implementing realtime features (broadcast, presence, channels, subscriptions) → `references/supabase-prompts-use-realtime.md`

Available but less common:

- Working with declarative schema (`supabase/schemas/` directory) → `references/supabase-prompts-declarative-database-schema.md`
- Creating migration files manually (`supabase/migrations/` directory) → `references/supabase-prompts-database-create-migration.md`

## Kiro Crew notes

- The hosted MCP server is registered by this app as `@supabase:supabase`. Its first use opens a Supabase sign-in in the browser.
- `references/supabase-hooks.md` describes Kiro IDE hooks (`.kiro/hooks/*.kiro.hook`). Kiro Crew does not use those files. When onboarding asks for hooks, offer to schedule the same checks (`get_advisors`, `get_logs`, Edge Function review) as Kiro Crew cron jobs instead, and only create them if the user agrees.
