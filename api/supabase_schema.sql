create extension if not exists pgcrypto;

create table if not exists public.notebooks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    title text not null default 'Untitled notebook',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.sources (
    id uuid primary key default gen_random_uuid(),
    notebook_id uuid not null references public.notebooks(id) on delete cascade,
    source_type text not null default 'pdf',
    file_name text not null,
    storage_path text not null,
    status text not null default 'indexing',
    created_at timestamptz not null default now(),
    constraint sources_source_type_check check (source_type in ('pdf', 'text', 'link')),
    constraint sources_status_check check (status in ('indexing', 'ready', 'failed'))
);

create table if not exists public.flashcards (
    id uuid primary key default gen_random_uuid(),
    notebook_id uuid not null references public.notebooks(id) on delete cascade,
    question text not null,
    answer text not null,
    card_order int not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists flashcards_notebook_id_order_idx
    on public.flashcards(notebook_id, card_order);

create table if not exists public.podcasts (
    id uuid primary key default gen_random_uuid(),
    notebook_id uuid not null references public.notebooks(id) on delete cascade,
    audio_url text not null,
    format text not null,
    language text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.mindmaps (
    id uuid primary key default gen_random_uuid(),
    notebook_id uuid not null references public.notebooks(id) on delete cascade,
    topic text not null,
    data jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    notebook_id uuid not null references public.notebooks(id) on delete cascade,
    role text not null,
    content text not null,
    sources_json jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    constraint messages_role_check check (role in ('user', 'assistant'))
);

create index if not exists notebooks_user_id_updated_at_idx
    on public.notebooks(user_id, updated_at desc);

create index if not exists sources_notebook_id_created_at_idx
    on public.sources(notebook_id, created_at);

create index if not exists messages_notebook_id_created_at_idx
    on public.messages(notebook_id, created_at);

create index if not exists podcasts_notebook_id_created_at_idx
    on public.podcasts(notebook_id, created_at);

create index if not exists mindmaps_notebook_id_created_at_idx
    on public.mindmaps(notebook_id, created_at);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_notebooks_updated_at on public.notebooks;

create trigger set_notebooks_updated_at
before update on public.notebooks
for each row
execute function public.set_updated_at();

create or replace function public.touch_notebook()
returns trigger
language plpgsql
as $$
begin
    update public.notebooks
    set updated_at = now()
    where id = new.notebook_id;
    return new;
end;
$$;

drop trigger if exists touch_notebook_on_source on public.sources;

create trigger touch_notebook_on_source
after insert or update on public.sources
for each row
execute function public.touch_notebook();

drop trigger if exists touch_notebook_on_message on public.messages;

create trigger touch_notebook_on_message
after insert on public.messages
for each row
execute function public.touch_notebook();

drop trigger if exists touch_notebook_on_podcast on public.podcasts;

create trigger touch_notebook_on_podcast
after insert on public.podcasts
for each row
execute function public.touch_notebook();

drop trigger if exists touch_notebook_on_mindmap on public.mindmaps;

create trigger touch_notebook_on_mindmap
after insert on public.mindmaps
for each row
execute function public.touch_notebook();

insert into storage.buckets (id, name, public)
values ('notebook-sources', 'notebook-sources', false)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('podcasts', 'podcasts', true)
on conflict (id) do nothing;
