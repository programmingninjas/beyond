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

## Five social worlds

The event room contains five connected, DOM-rendered worlds: Discovery Plaza, Conversation Café, Connection Garden, Activity Arcade, and Idea Lab. Plaza is the hub; spatial portals connect it to the other four rooms. Each world uses canonical 1920×1080 coordinates with responsive contain/letterbox rendering. Room bounds, colliders, movement validation, safe spawns, seats, portals, and interaction zones are server-owned in `backend/worlds/*.json`. Nearby presence and private chat stay scoped to the current event and room.

World art is layered and swappable. Each `frontend/public/worlds/<room>/` folder has `background`, `ground`, `midground`, and `foreground` files and a `manifest.json` with layer order, dimensions, placeholder status, and SHA-256 hashes. The current SVGs are engineering placeholders, not collision maps. To replace a layer, keep its room/layer ID, file path, 1920×1080 coordinate frame, and order; update its manifest checksum. Validate the files and backend references with `cd frontend && npm run validate:world-assets`. See [the asset pipeline notes](frontend/public/worlds/README.md) and [geometry migration notes](backend/worlds/MIGRATION.md).

### World development flags

All flags are off by default.

- `NEXT_PUBLIC_WORLD_ROOM_TABS=1` enables development-only direct room tabs. This is a build-time flag; when using Compose, pass it as a build argument (for example `NEXT_PUBLIC_WORLD_ROOM_TABS=1 docker compose build web`). The backend also requires `WORLD_ALLOW_ROOM_SWITCH=1` to accept the legacy room-switch message.
- `NEXT_PUBLIC_WORLD_DEBUG=1` enables the geometry overlay by default at build time. It displays bounds, colliders, spawns, portals, and interaction zones.
- Add `?worldDebug=1` to the running app URL to enable the overlay at runtime without rebuilding. This query flag is independent of the build-time flag.
- Compose maps `NEXT_PUBLIC_WORLD_ROOM_TABS`, `NEXT_PUBLIC_WORLD_DEBUG`, and `WORLD_ALLOW_ROOM_SWITCH` to their respective build/runtime settings. Each defaults to `0`.

### World tests

Run backend tests in Compose after building the API image:

```sh
docker compose build
docker compose run --rm api sh -c "pip install -r requirements-dev.txt && pytest -q"
```

Run frontend tests and the production build from `frontend/`:

```sh
npm ci
npm run test
npm run build
```

`npm run test` uses Vitest for the coordinate transforms, letterboxing, interaction selection, layer ordering, reduced-motion behavior, and config-revision recovery.

## Development notes

The API creates its tables on startup. Its default database when run outside Compose is local SQLite (`DATABASE_URL` overrides it); production migrations and deployment are out of scope. The real-time room and application update channel keep their subscribers in the API process, so the MVP must run with a single API worker. For multiple workers or API instances, replace the in-process update channel and room presence with a shared pub/sub service. Room membership is checked when connecting, and connections close at the event start time. JWTs are stored in browser local storage for this local MVP; use hardened sessions, HTTPS, a strong signing key, rate limiting, migrations, and a shared presence service before production deployment.

## V2 development status

The application adds account networking profiles, event personas, pet preferences, discovery opt-out, blocks, and consent records. Additive migrations run on startup and preserve existing PostgreSQL and SQLite rows; back up your database before upgrading.

Set `OPENAI_API_KEY` in the environment before starting Compose to enable live matching and pet conversations. `OPENAI_MODEL` defaults to `gpt-4o-mini`. Matching and conversations use background jobs and persist their results; errors are shown in the UI. Without a key, the rest of the application continues to run and AI jobs report that the key is missing. Only explicitly selected fields are sent for a pet conversation after both participants approve. Existing direct connection requests remain available.

To add a **fictional, precomputed** demonstration event, run `docker compose exec api python seed_demo.py`. Sign in with `demo.alex@example.test` or `demo.devon@example.test`, using password `BeyondDemo2026!`. The demo's cached results are labeled and do not use an API key. To use the latest code, rebuild and restart the containers first.

V2 is still incomplete: structured persona extraction, robust matchmaking evaluation and cost controls, a production-ready worker, complete animation assets and conservation passports, world activities and moderation, and a fully accessible proximity meter remain to be implemented. The five worlds have configured movement, collision, portals, seats, and room-specific presence; several activities and all final environment art remain placeholders. The existing single-worker and local-development security limitations still apply.
