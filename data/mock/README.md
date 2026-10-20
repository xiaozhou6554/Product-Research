# Fixed data

The application uses the versioned fixture adapter in `backend/app/infrastructure/fixtures.py` for local evaluation. Any future CSV import must preserve `source_type`, `source_version`, `marketplace`, `fetched_at`, and `raw_record_hash` metadata.
