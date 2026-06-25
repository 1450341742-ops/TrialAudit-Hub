-- TrialAudit Hub Supabase schema
-- Run this file once in Supabase Dashboard > SQL Editor.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  project_code text not null unique,
  sponsor_project_code text,
  sponsor_name text,
  center_name text,
  sponsor_type text not null default '未分类',
  center_type text not null default '未分类',
  phase text,
  therapeutic_area text,
  visit_count numeric(10,2) not null default 1,
  case_count integer not null default 0,
  project_manager text,
  status text not null default '待确认',
  risk_level text not null default '低',
  planned_start_date date,
  planned_end_date date,
  actual_start_date date,
  actual_end_date date,
  source_year integer,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.project_flows (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null unique references public.projects(id) on delete cascade,
  project_code text not null,
  lead_auditor text,
  auditors text[] not null default '{}',
  audit_time_text text,
  audit_start_date date,
  audit_end_date date,
  startup_letter_date date,
  cra_contact text,
  materials_status text,
  dingpan_status text,
  edc_status text,
  finance_status text,
  business_info_status text,
  qualification_status text,
  confirmation_letter_date date,
  thank_you_letter_date date,
  report_due_date date,
  report_status text,
  capa_due_date date,
  capa_status text,
  status text not null default '待确认',
  express_no text,
  finalized boolean not null default false,
  collection_count integer not null default 0,
  contract_amount numeric(14,2) not null default 0,
  received_amount numeric(14,2) not null default 0,
  ding_upload_status text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.auditors (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  employment_type text not null default '正式',
  level text,
  monthly_visit_limit integer not null default 4,
  active boolean not null default true,
  phone text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.schedules (
  id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  auditor_id uuid references public.auditors(id) on delete set null,
  auditor_name text not null,
  project_id uuid references public.projects(id) on delete set null,
  project_code text,
  work_date date not null,
  availability_status text not null default '占用',
  role text,
  city text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.parttime_entries (
  id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  auditor_id uuid references public.auditors(id) on delete set null,
  auditor_name text not null,
  project_id uuid references public.projects(id) on delete set null,
  project_code text,
  period_month date not null,
  work_start_date date,
  work_end_date date,
  work_days numeric(10,2) not null default 0,
  daily_rate numeric(14,2) not null default 0,
  adjustment_amount numeric(14,2) not null default 0,
  actual_paid numeric(14,2) not null default 0,
  payment_status text not null default '待确认',
  payment_date date,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.monthly_targets (
  id uuid primary key default gen_random_uuid(),
  year integer not null,
  month integer not null check (month between 1 and 12),
  planned_visits numeric(10,2) not null default 0,
  actual_visits numeric(10,2) not null default 0,
  annual_target numeric(10,2) not null default 300,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(year, month)
);

create table if not exists public.import_batches (
  id uuid primary key default gen_random_uuid(),
  file_name text not null,
  data_type text not null,
  storage_path text,
  row_count integer not null default 0,
  success_count integer not null default 0,
  failed_count integer not null default 0,
  notes text,
  imported_at timestamptz not null default now()
);

create index if not exists idx_projects_status on public.projects(status);
create index if not exists idx_projects_source_year on public.projects(source_year);
create index if not exists idx_projects_center_name on public.projects(center_name);
create index if not exists idx_flows_report_due on public.project_flows(report_due_date);
create index if not exists idx_flows_capa_due on public.project_flows(capa_due_date);
create index if not exists idx_schedules_work_date on public.schedules(work_date);
create index if not exists idx_schedules_auditor on public.schedules(auditor_name);
create index if not exists idx_parttime_period on public.parttime_entries(period_month);

create or replace trigger projects_set_updated_at
before update on public.projects
for each row execute function public.set_updated_at();

create or replace trigger project_flows_set_updated_at
before update on public.project_flows
for each row execute function public.set_updated_at();

create or replace trigger auditors_set_updated_at
before update on public.auditors
for each row execute function public.set_updated_at();

create or replace trigger schedules_set_updated_at
before update on public.schedules
for each row execute function public.set_updated_at();

create or replace trigger parttime_entries_set_updated_at
before update on public.parttime_entries
for each row execute function public.set_updated_at();

create or replace trigger monthly_targets_set_updated_at
before update on public.monthly_targets
for each row execute function public.set_updated_at();

alter table public.projects enable row level security;
alter table public.project_flows enable row level security;
alter table public.auditors enable row level security;
alter table public.schedules enable row level security;
alter table public.parttime_entries enable row level security;
alter table public.monthly_targets enable row level security;
alter table public.import_batches enable row level security;

-- This internal Streamlit application uses the service-role key on the server.
-- No anon/authenticated policies are created, so browser-side public access remains blocked.
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;

insert into storage.buckets (id, name, public)
values ('source-files', 'source-files', false)
on conflict (id) do nothing;
