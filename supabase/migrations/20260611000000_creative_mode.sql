-- Aijolot Banner Agent — C0: creative mode plumbing
-- The agent RECOMMENDS the creative mode (composite | full_picture | video) and
-- whether humans appear in the imagery; the user can override it (mode_source
-- = 'user' is never overwritten by a re-recommendation). The resolved mode
-- travels inside the revision concept's art_direction (plan → build contract).

alter table public.art_directions
  add column if not exists creative_mode  text not null default 'composite'
    check (creative_mode in ('composite', 'full_picture', 'video')),
  add column if not exists include_humans boolean not null default false,
  add column if not exists mode_rationale text,
  add column if not exists mode_source    text not null default 'agent'
    check (mode_source in ('agent', 'user'));
