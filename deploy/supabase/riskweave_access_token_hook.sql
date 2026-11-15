-- RiskWeave: Supabase custom access token hook.
--
-- The RiskWeave API verifies RS256 tokens that carry `aud`, `scope` and `nbf`.
-- Supabase OAuth access tokens have aud "authenticated", no custom scope and no nbf,
-- so this hook adds them -- but only for tokens issued to the RiskWeave console's
-- OAuth client, and only for users an operator marked as analysts:
--
--   update auth.users
--      set raw_app_meta_data = raw_app_meta_data || '{"riskweave_analyst": true}'
--    where email = 'analyst@example.com';
--
-- Before running: replace REPLACE_WITH_RISKWEAVE_CLIENT_ID below with the client ID
-- from Authentication > OAuth Server > Clients. Then enable it under
-- Authentication > Hooks > Customize Access Token (JWT) Claims and select
-- public.riskweave_access_token_hook.

create or replace function public.riskweave_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
set search_path = ''
as $$
declare
  claims jsonb := event -> 'claims';
  client text := coalesce(event ->> 'client_id', claims ->> 'client_id');
begin
  if client = 'REPLACE_WITH_RISKWEAVE_CLIENT_ID'
     and coalesce((claims -> 'app_metadata' ->> 'riskweave_analyst')::boolean, false)
  then
    claims := jsonb_set(claims, '{aud}', '"riskweave-api"');
    claims := jsonb_set(claims, '{scope}', '"ringsentinel:analyst"');
    claims := jsonb_set(claims, '{nbf}', claims -> 'iat');
  end if;
  return jsonb_build_object('claims', claims);
end;
$$;

-- Only Supabase Auth may run the hook; never expose it through the Data API.
grant execute on function public.riskweave_access_token_hook(jsonb) to supabase_auth_admin;
revoke execute on function public.riskweave_access_token_hook(jsonb) from authenticated, anon, public;
grant usage on schema public to supabase_auth_admin;
