create extension if not exists pgcrypto;

create table if not exists companies (
    company_number text primary key,
    company_name text not null,
    company_name_normalized text not null,
    company_status text,
    date_of_creation date,
    sic_codes jsonb not null default '[]'::jsonb,
    registered_office jsonb not null default '{}'::jsonb,
    latest_stream_timepoint bigint,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    enrichment_status text not null default 'pending',
    enrichment_completed_at timestamptz,
    updated_at timestamptz not null default now()
);

create table if not exists raw_events (
    id uuid primary key default gen_random_uuid(),
    stream_name text not null,
    event_hash text not null unique,
    resource_id text,
    event_type text,
    timepoint bigint,
    published_at timestamptz,
    payload jsonb not null,
    received_at timestamptz not null default now(),
    processing_status text not null default 'stored',
    processing_error text
);

create index if not exists raw_events_stream_timepoint_idx on raw_events(stream_name, timepoint);

create table if not exists stream_checkpoints (
    stream_name text primary key,
    timepoint bigint,
    connection_status text not null default 'never_connected',
    last_event_at timestamptz,
    last_heartbeat_at timestamptz,
    reconnect_count integer not null default 0,
    last_error text,
    updated_at timestamptz not null default now()
);

create table if not exists enrichment_jobs (
    id uuid primary key default gen_random_uuid(),
    company_number text not null references companies(company_number) on delete cascade,
    enrichment_scope text not null default 'initial_rest',
    status text not null default 'pending',
    attempts integer not null default 0,
    last_error text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    unique(company_number, enrichment_scope)
);

create index if not exists enrichment_jobs_queue_idx on enrichment_jobs(status, created_at);

create table if not exists officers (
    officer_key text primary key,
    name text,
    nationality text,
    country_of_residence text,
    address_country text,
    raw_data jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists company_officers (
    company_number text not null references companies(company_number) on delete cascade,
    officer_key text not null references officers(officer_key) on delete cascade,
    role text,
    appointed_on date,
    resigned_on date,
    raw_data jsonb not null default '{}'::jsonb,
    primary key(company_number, officer_key)
);

create table if not exists psc_entities (
    psc_key text primary key,
    kind text not null,
    name text,
    nationality text,
    country_of_residence text,
    country_registered text,
    legal_form text,
    raw_data jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists company_pscs (
    company_number text not null references companies(company_number) on delete cascade,
    psc_key text not null references psc_entities(psc_key) on delete cascade,
    ceased_on date,
    raw_data jsonb not null default '{}'::jsonb,
    primary key(company_number, psc_key)
);

create table if not exists screening_rules (
    id uuid primary key default gen_random_uuid(),
    rule_type text not null,
    rule_value text not null,
    enabled boolean not null default true,
    version integer not null default 1,
    created_at timestamptz not null default now(),
    unique(rule_type, rule_value)
);

create table if not exists lead_matches (
    id uuid primary key default gen_random_uuid(),
    company_number text not null references companies(company_number) on delete cascade,
    match_type text not null,
    match_value text,
    reason text not null,
    target_country text,
    evidence_type text,
    restricted_sic_qualified boolean,
    created_at timestamptz not null default now(),
    unique(company_number, match_type, match_value, evidence_type)
);

create table if not exists shortlist (
    company_number text primary key references companies(company_number) on delete cascade,
    selected_by text not null,
    status text not null default 'shortlisted',
    notes text,
    tags jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists worker_status (
    worker_name text primary key,
    process_id text,
    status text not null default 'stopped',
    heartbeat_at timestamptz,
    last_event_at timestamptz,
    last_commit_at timestamptz,
    queue_depth integer not null default 0,
    events_received bigint not null default 0,
    events_committed bigint not null default 0,
    last_error text,
    updated_at timestamptz not null default now()
);

create table if not exists notification_log (
    id uuid primary key default gen_random_uuid(),
    company_number text not null references companies(company_number) on delete cascade,
    notification_type text not null default 'in_app_new_lead',
    message text not null,
    read_at timestamptz,
    created_at timestamptz not null default now(),
    unique(company_number, notification_type)
);
