-- OPTIONAL: Run in Supabase SQL Editor as an admin, NOT as app_user.
-- Creates a profile row when a user signs up. Uses the current auth.users UUID.
-- Be sure to test on a staging project first.
create or replace function public.handle_new_user_profile()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.dim_user_profile (user_id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'username', ''))
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_profile on auth.users;
create trigger on_auth_user_created_profile
  after insert on auth.users
  for each row execute function public.handle_new_user_profile();
