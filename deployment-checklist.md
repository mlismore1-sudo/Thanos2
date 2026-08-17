# Thanos deployment checklist

## 1. Upload

Upload the generated files to the new `Thanos` repository, preserving these paths:

```text
app.py
requirements.txt
.env.example
.gitignore
README.md
config/buzzwords.txt
config/restricted_sic_codes.txt
config/target_countries.json
db/migrations/001_initial_schema.sql
src/__init__.py
src/auth.py
src/companies_house_rest.py
src/companies_house_stream.py
src/config.py
src/database.py
src/enrichment.py
src/screening.py
src/worker.py
tests/test_screening.py
```

Rename downloaded files where necessary:

- `env.example.txt` → `.env.example`
- `gitignore.txt` → `.gitignore`

## 2. New Supabase project

Create the new Supabase project. Open its SQL editor and run `db/migrations/001_initial_schema.sql`. Verify that the tables were created in the new project only.

## 3. Streamlit secrets

Add these values to the new Streamlit deployment:

```text
DATABASE_URL
COMPANIES_HOUSE_STREAM_API_KEY
COMPANIES_HOUSE_REST_API_KEY
APP_PASSWORD_HASH
SESSION_SECRET
```

Do not use credentials from the old app.

## 4. Password hash

Generate a bcrypt hash locally rather than putting the plaintext password in GitHub. For example:

```python
import bcrypt
print(bcrypt.hashpw(b"YOUR_PASSWORD", bcrypt.gensalt()).decode())
```

Put the output in the new deployment secret named `APP_PASSWORD_HASH`.

## 5. First test

Initially set:

```text
STREAM_ENABLED=false
ENRICHMENT_ENABLED=false
```

Deploy and verify that login and the dashboard load. Then enable enrichment and test with a small controlled run. Finally enable the stream.

## 6. Security

Never commit `.env`, API keys, database URLs, password text, or Streamlit secrets. Do not run the SQL migration against the existing app's database.
