# Beyond

A local-development event networking MVP. One account can host events and attend others. Participants take an event-specific placeholder quiz, discover people, connect, message, and meet in a real-time room before the event begins.

## Run locally

Install Docker and Docker Compose, then run:

```sh
docker compose up --build
```

Open http://localhost:3000. The API and interactive API documentation are at http://localhost:8000/docs. PostgreSQL data persists in the `postgres_data` Docker volume. Set `SECRET_KEY` in your environment before starting Compose to override the development signing key. `NEXT_PUBLIC_API_URL` is compiled into the web image and defaults to `http://localhost:8000`; `FRONTEND_ORIGIN` controls API CORS. Event times entered in the browser are converted from the browser's local time to UTC for storage.

Create an account, create and publish an event, then use a second account to register and take the quiz. The organizer can edit the placeholder quiz as JSON or reload the included template. Quiz edits are locked after the first completed result to keep results consistent. Ties use the first personality listed in the quiz. The room is available after quiz completion and closes at the event start time. Use WASD or the arrow keys to walk (touch controls are available on small screens). Walk near another participant and select their name to chat; nearby conversations are ephemeral, while direct messages between accepted connections persist.

The bundled quiz and personality labels are placeholders and have no claim of scientific accuracy. The profile enrichment provider is an interface only: no external profile is fetched. Consent can be recorded for a future integration, which must check it before making a request.

## Development notes

The API creates its tables on startup. Its default database when run outside Compose is local SQLite (`DATABASE_URL` overrides it); production migrations and deployment are out of scope. The real-time room and application update channel keep their subscribers in the API process, so the MVP must run with a single API worker. For multiple workers or API instances, replace the in-process update channel and room presence with a shared pub/sub service. Room membership is checked when connecting, and connections close at the event start time. JWTs are stored in browser local storage for this local MVP; use hardened sessions, HTTPS, a strong signing key, rate limiting, migrations, and a shared presence service before production deployment.

## V2 development status

The application adds account networking profiles, event personas, pet preferences, discovery opt-out, blocks, and consent records. Additive migrations run on startup and preserve existing PostgreSQL and SQLite rows; back up your database before upgrading.

Set `OPENAI_API_KEY` in the environment before starting Compose to enable live matching and pet conversations. `OPENAI_MODEL` defaults to `gpt-4o-mini`. Matching and conversations use background jobs and persist their results; errors are shown in the UI. Without a key, the rest of the application continues to run and AI jobs report that the key is missing. Only explicitly selected fields are sent for a pet conversation after both participants approve. Existing direct connection requests remain available.

To add a **fictional, precomputed** demonstration event, run `docker compose exec api python seed_demo.py`. Sign in with `demo.alex@example.test` or `demo.devon@example.test`, using password `BeyondDemo2026!`. The demo's cached results are labeled and do not use an API key. To use the latest code, rebuild and restart the containers first.

V2 is still incomplete: structured persona extraction, robust matchmaking evaluation and cost controls, a production-ready worker, complete animation assets and conservation passports, world activities and moderation, and a fully accessible proximity meter remain to be implemented. The five rooms currently provide placeholders and room-specific presence; they do not yet provide the planned activities or collision maps. The existing single-worker and local-development security limitations still apply.
