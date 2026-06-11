-- Idioma del equipo (es/en): controla el idioma de TODO lo que el agente
-- produce fuera de una campaña (sugerencias proactivas de calendario, catálogo
-- y performance). Las campañas llevan su propio language en structured_brief.
alter table public.team_calendar_settings
  add column if not exists lang text not null default 'es' check (lang in ('es', 'en'));
