-- Aijolot Banner Agent — F1: proactive commercial calendar
-- Global recurring dates (MX-first + global, team_id null) + team-scoped
-- inferred/manual events, and per-team scan settings. The calendar_scan agent
-- job turns upcoming events into agent_suggestions with a prefilled brief.

create table public.commercial_calendar_events (
  id              uuid primary key default gen_random_uuid(),
  team_id         uuid references public.teams(id) on delete cascade,  -- null = global seed
  slug            text not null,
  name            text not null,
  country         text not null default 'MX',
  -- Recurring annual events (global seed): month/day + duration.
  month           smallint check (month between 1 and 12),
  day             smallint check (day between 1 and 31),
  duration_days   integer not null default 7,
  -- One-shot events (niche_inferred / manual): explicit dates.
  starts_on       date,
  ends_on         date,
  source          text not null default 'seed' check (source in ('seed', 'niche_inferred', 'manual')),
  relevance_note  text,
  created_at      timestamptz not null default now()
);

create unique index commercial_calendar_events_uidx
  on public.commercial_calendar_events (coalesce(team_id::text, 'global'), slug);

alter table public.commercial_calendar_events enable row level security;
create policy calendar_events_select on public.commercial_calendar_events
  for select using (team_id is null or public.is_team_member(team_id));
create policy calendar_events_member_write on public.commercial_calendar_events
  for all using (team_id is not null and public.is_team_member(team_id))
  with check (team_id is not null and public.is_team_member(team_id));

create table public.team_calendar_settings (
  team_id         uuid primary key references public.teams(id) on delete cascade,
  lead_time_days  integer not null default 14,
  auto_concept    boolean not null default false,
  enabled         boolean not null default true,
  updated_at      timestamptz not null default now()
);

alter table public.team_calendar_settings enable row level security;
create policy team_calendar_settings_rw on public.team_calendar_settings
  for all using (public.is_team_member(team_id)) with check (public.is_team_member(team_id));

-- Seed: México-first + global retail dates (recurring annually).
insert into public.commercial_calendar_events (slug, name, country, month, day, duration_days, source, relevance_note) values
  ('dia-de-reyes',        'Día de Reyes',                 'MX',     1,  6,  3, 'seed', 'Regalos de Reyes — última campaña de la temporada navideña.'),
  ('san-valentin',        'San Valentín',                 'GLOBAL', 2, 14,  7, 'seed', 'Regalos de pareja y autorregalo.'),
  ('dia-de-las-madres',   'Día de las Madres (MX)',       'MX',     5, 10,  7, 'seed', 'Una de las fechas de mayor venta del retail mexicano.'),
  ('hot-sale',            'Hot Sale MX',                  'MX',     5, 26,  6, 'seed', 'El evento de ecommerce más grande de México.'),
  ('dia-del-padre',       'Día del Padre',                'MX',     6, 21,  7, 'seed', 'Tercer domingo de junio (aprox).'),
  ('regreso-a-clases',    'Regreso a clases',             'MX',     8, 15, 21, 'seed', 'Útiles, ropa, tecnología y accesorios.'),
  ('el-buen-fin',         'El Buen Fin',                  'MX',    11, 13,  5, 'seed', 'El fin de semana más barato del año (aprox segunda quincena de noviembre).'),
  ('black-friday-cyber',  'Black Friday + Cyber Monday',  'GLOBAL',11, 27,  5, 'seed', 'BFCM — pico global de descuentos.'),
  ('navidad',             'Navidad',                      'GLOBAL',12, 24,  8, 'seed', 'Campañas de regalos navideños y envío garantizado.');
