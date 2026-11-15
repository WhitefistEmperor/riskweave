-- RiskWeave: keep case data out of Supabase's auto-generated Data API.
--
-- RiskWeave's migrations create their tables in the `public` schema, which Supabase
-- exposes over its Data API to anyone holding the public (publishable/anon) key.
-- The API connects as `postgres`, which owns these tables and so bypasses RLS; thus
-- enabling RLS with no policies denies the Data API roles without affecting RiskWeave.
--
-- Run after every `ringsentinel-migrate`, since new migrations can add tables.
-- Also recommended: Project Settings > Data API > turn the Data API off entirely
-- (the consent page only uses Supabase Auth, not the Data API).

do $$
declare
  item record;
begin
  for item in
    select tablename from pg_tables where schemaname = 'public'
  loop
    execute format('alter table public.%I enable row level security', item.tablename);
    execute format('revoke all on table public.%I from anon, authenticated', item.tablename);
  end loop;
end;
$$;

-- Verify: this must return zero rows.
select tablename from pg_tables where schemaname = 'public' and not rowsecurity;
