# Thanos — Companies House Lead Screening

Thanos is a new, isolated Companies House lead-screening application. It must use a completely separate Supabase project, GitHub repository, Streamlit deployment, database connection, and API credentials from the existing application.

## Intended behaviour

- Consume the Companies House company stream for immediate discovery.
- Display a company immediately when its SIC code or name matches a configured rule.
- Use whole-token, case-insensitive buzzword matching.
- Enrich every streamed company once through the Companies House REST API.
- Store officer nationality, country of residence, address country, PSC data, and corporate ownership evidence.
- Persist raw events and stream checkpoints in PostgreSQL.
- Show worker health and enrichment status in Streamlit.
- Support Brad/James login using one shared password.
- Support shortlisting, notes, in-app notifications, and CSV export.

## Repository structure

```text
Thanos/
├── .env.example
├── .gitignore
├── README.md
├── app.py
├── requirements.txt
├── config/
│   ├── buzzwords.txt
│   ├── restricted_sic_codes.txt
│   └── target_countries.json
├── db/
│   └── migrations/
│       └── 001_initial_schema.sql
├── src/
│   ├── __init__.py
│   ├── auth.py
│   ├── companies_house_rest.py
│   ├── companies_house_stream.py
│   ├── config.py
│   ├── database.py
│   ├── enrichment.py
│   ├── screening.py
│   └── worker.py
└── tests/
    └── test_screening.py
```

## Required secrets

Configure these only in the new Streamlit deployment:

```text
DATABASE_URL
COMPANIES_HOUSE_STREAM_API_KEY
COMPANIES_HOUSE_REST_API_KEY
APP_PASSWORD_HASH
SESSION_SECRET
```

Never commit `.env`, API keys, Supabase credentials, plaintext passwords, or Streamlit secrets.

## Initial deployment sequence

1. Create the new Supabase project.
2. Run `db/migrations/001_initial_schema.sql` in that new project only.
3. Configure the new Streamlit secrets.
4. Deploy with `STREAM_ENABLED=false` and `ENRICHMENT_ENABLED=false`.
5. Verify login and dashboard loading.
6. Enable enrichment and test REST access.
7. Enable the stream after the dashboard and database connection are confirmed.

## Safety

This repository must never be pointed at the existing app's database, deployment, credentials, or source files. The existing app remains untouched and operational.
