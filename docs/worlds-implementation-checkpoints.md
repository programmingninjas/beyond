# Worlds implementation checkpoint evidence

This checkpoint records the already completed extraction, canonical configuration, coordinate, collision, portal, interaction, and placeholder-asset work. The repository was unchanged from audit commit `1589168b9f6a284b7b03fbf9a497343fdd622eee`.

## Baseline

`python -m pytest backend/tests -q` stopped during collection:

```text
ModuleNotFoundError: No module named 'fastapi'
```

`npm run build` stopped before invoking Next.js:

```text
'next' is not recognized as an internal or external command,
operable program or batch file.
```

## Step 3 checkpoint

- Backend-owned world JSON exists for `plaza`, `cafe`, `garden`, `arcade`, and `lab`.
- The API serves `GET /worlds` and `GET /worlds/{room_id}`.
- Config startup validation and `/worlds` tests passed in the backend suite.

## Step 5 checkpoint

- Movement uses 1920×1080 world units, a 28-unit participant radius, 250 units/second, swept checks, and server correction messages.
- Tests cover a thin-wall sweep, out-of-bounds and impossible-speed rejection, NaN rejection, and a portal transition with a server-selected spawn.
- A two-client WebSocket test covers proximity chat, distance rejection, and blocks.

## Test evidence at this checkpoint

```text
py -3.12 -m pytest backend/tests -q
8 passed, 18 warnings in 9.76s
```

```text
npm run build
✓ Compiled successfully
✓ Generating static pages (4/4)
○  (Static) prerendered as static content
```

Warnings are from the existing FastAPI event hooks and the repository's development JWT key length.

## Addendum completion evidence

Work continued on `feat/worlds` from checkpoint commit `cec88f1`; the earlier implementation was not restarted or reverted. `git log -1` initially showed the audit revision `1589168b9f6a284b7b03fbf9a497343fdd622eee`, matching `repo-revision.txt`. The addendum fixes are in the follow-up commit recorded with this report.

### Backend

Command (run from `backend/`): `py -3.12 -m pytest -q`

```text
.............                                                            [100%]
13 passed, 6 warnings in 9.62s
```

Command: `py -3.12 -m pip install -r requirements.txt -r requirements-dev.txt`

The install did not complete in this environment: pip repeatedly timed out while downloading the 2.9 MB `psycopg_binary-3.2.3` wheel and was stopped after repeated retries. The backend tests above ran against the already-installed Python 3.12 environment. Runtime requirements remain unchanged; pytest and httpx are isolated in `requirements-dev.txt`.

### Frontend

Command (run from `frontend/`): `npm ci`

```text
added 75 packages, and audited 76 packages in 37s
9 vulnerabilities (3 moderate, 3 high, 3 critical)
```

Command: `npm run test && npm run build`

```text
✓ lib/world/world.test.ts (3 tests)
Test Files  1 passed (1)
Tests  3 passed (3)
✓ Compiled successfully
✓ Generating static pages (4/4)
○  (Static) prerendered as static content
```

Command: `npm run validate:world-assets`

```text
World configs and 20 environment placeholder layers validated.
```

The npm audit findings are from the existing pinned dependency tree, including the existing Next.js 15.1.4 version; no dependency was added except Vitest and no broad dependency upgrade was made.

### Manual visual checks

No Playwright screenshot matrix was captured. Playwright is not present, and the addendum permits only Vitest as a new dependency. The available browser path would require signing into the app; the computer-use instructions prohibit automating authentication. The five-room art/interaction review at 1440×900 and 390×844, including the debug overlay screenshot, remains a manual follow-up. Automated server tests cover portal thresholds and safe destinations, both bridge crossings/rails, movement validation, event-scoped presence, nearby private chat, and block hiding on the next snapshot.
