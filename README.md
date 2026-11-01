# Beyond

A local-development event networking MVP. One account can host events and attend others. Participants complete an account profile, discover people, connect, message, and meet in a real-time room before the event begins.

## Run locally

Install Docker and Docker Compose, then create `.env` from `.env.example` if it does not already exist. Add your `OPENAI_API_KEY` and `EXA_API_KEY` to `.env`, then run:

```sh
docker compose up --build
```

Open http://localhost:3000. The API and interactive API documentation are at http://localhost:8000/docs. PostgreSQL data persists in the `postgres_data` Docker volume. Set `SECRET_KEY` in your environment before starting Compose to override the development signing key. The browser client uses the hostname you opened for API requests, and `FRONTEND_ORIGIN` configures the API CORS origin. Event times entered in the browser are converted from the browser's local time to UTC for storage.

To open the app from another device on the same Wi-Fi, use the host computer's LAN address, for example `http://192.168.1.20:3000`. The browser client uses the page hostname for API requests, and the API permits local-network origins on port 3000. Find the Mac's current Wi-Fi address with `ipconfig getifaddr en0`; the address can change when it reconnects to Wi-Fi.

Create an account and complete the basic profile before registering for a new event: name, email, phone, a social profile URL, a 100–1,000 character About Me, and at least one interest. Existing registrations remain valid. Organizers can add short-answer registration questions and view responses; questions lock after the first registration. The personality quiz is optional for registration and completed once at account level. Its questions and scoring remain placeholders.

Profile completeness currently uses provisional weights: 25 points for all basic fields, 5 points each for 12 additional fields, and 15 points for the personality quiz. The complete-profile badge requires every field and the quiz. The minimum checks the complete basic section independently of the score. Phone numbers are not included in public profiles, matching input, or pet sharing.

Rooms are available to registered attendees before the event starts. Use WASD or arrow keys to walk; touch controls are available on small screens. Nearby conversations are ephemeral, while direct messages between accepted connections persist. Historical event quizzes and results remain in the database but are no longer used for onboarding.

## Development notes

The API applies additive versioned migrations on startup. Its default database when run outside Compose is local SQLite (`DATABASE_URL` overrides it); production deployment is out of scope. The real-time room and application update channel keep their subscribers in the API process, so the MVP must run with a single API worker. For multiple workers or API instances, replace the in-process update channel and room presence with a shared pub/sub service. Room membership is checked when connecting, and connections close at the event start time. JWTs are stored in browser local storage for this local MVP; use hardened sessions, HTTPS, a strong signing key, rate limiting, migrations, and a shared presence service before production deployment.

## V2 development status

The application adds account networking profiles, event personas, pet preferences, discovery opt-out, blocks, and consent records. Additive migrations run on startup and preserve existing PostgreSQL and SQLite rows; back up your database before upgrading.

Set `OPENAI_API_KEY` in `.env` before starting Compose to enable live matching and pet conversations. Set both `OPENAI_API_KEY` and `EXA_API_KEY` to enable the optional profile import. `OPENAI_MODEL` defaults to `gpt-4o-mini`. Matching and conversations use background jobs and persist their results; errors are shown in the UI. Without a key, the rest of the application continues to run and AI jobs report that the key is missing. Pet sharing preferences are saved in **Pet introductions** and control which profile fields are included in a request or approval. Both participants must approve before a conversation is generated, and only the approved fields are sent. Existing direct connection requests remain available.

To add a **fictional, precomputed** demonstration event, run `docker compose exec api python seed_demo.py`. Sign in with `demo.alex@example.com` or `demo.devon@example.com`, using password `BeyondDemo2026!`. The demo's cached results are labeled and do not use an API key. To use the latest code, rebuild and restart the containers first.

V2 is still incomplete: structured persona extraction, robust matchmaking evaluation and cost controls, a production-ready worker, complete animation assets and conservation passports, world activities and moderation, and a fully accessible proximity meter remain to be implemented. The five rooms currently provide placeholders and room-specific presence; they do not yet provide the planned activities or collision maps. The existing single-worker and local-development security limitations still apply.

## Import a public profile

In My profile, enter a public HTTPS link, explicitly consent, and choose Preview profile suggestions. Exa retrieves only the supplied link; OpenAI extracts suggested fields. No suggestion is saved until you select and apply it. The preview shows existing values and can be edited; save other profile edits before importing because applying suggestions reloads the profile form. Applied fields store their source URL and import time. If a field is manually changed later, its import attribution is cleared. The import does not fetch private or login-only content and may fail for some sites.

For a copy of this project, use `cp .env.example .env` and fill in both keys locally. `.env` is ignored by Git. Restart the API with `docker compose up -d --build` after changing keys. Do not paste keys into chat.
