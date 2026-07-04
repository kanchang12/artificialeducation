-- Run this in Supabase SQL editor

create table if not exists profiles (
  id uuid references auth.users on delete cascade primary key,
  full_name text,
  plan text default 'free' check (plan in ('free','premium')),
  plan_cancel_pending boolean default false,
  credits_minutes numeric default 0,
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz default now()
);

-- If table already existed from earlier setup, add the new columns:
alter table profiles add column if not exists plan_cancel_pending boolean default false;
alter table profiles add column if not exists credits_minutes numeric default 0;
alter table profiles add column if not exists stripe_customer_id text;
alter table profiles add column if not exists stripe_subscription_id text;

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, new.raw_user_meta_data->>'full_name');
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- RLS
alter table profiles enable row level security;
drop policy if exists "Users can read own profile" on profiles;
drop policy if exists "Users can update own profile" on profiles;
create policy "Users can read own profile" on profiles for select using (auth.uid() = id);
create policy "Users can update own profile" on profiles for update using (auth.uid() = id);

-- Note: server-side credit/plan writes use the SERVICE ROLE key (bypasses RLS),
-- so the policies above only matter for any direct client-side Supabase access.

-- Admin-editable cost settings (Koyeb, Supabase, Gemini, Domain, Marketing)
create table if not exists settings (
  key text primary key,
  value text
);
alter table settings enable row level security;
-- No public policies - only accessed via service role key from admin routes

-- Per-student course assignment: admin assigns specific builds to specific
-- students. If a student has zero rows here, they fall back to the normal
-- free/credits unlock rule everywhere else. The moment a student has ANY
-- row here, their builds list is restricted to free builds + assigned builds.
create table if not exists course_assignments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users on delete cascade not null,
  build_id text not null,
  assigned_at timestamptz default now(),
  unique (user_id, build_id)
);
alter table course_assignments enable row level security;
-- No public policies - only accessed via service role key from admin routes
