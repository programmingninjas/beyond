# Worlds implementation checkpoint evidence

This checkpoint records the already completed extraction, canonical configuration, coordinate, collision, portal, interaction, and placeholder-asset work. The repository was unchanged from audit commit `1589168b9f6a284b7b03fbf9a497343fdd622eee`.

## Baseline

### Pre-container baseline

`python -m pytest backend/tests -q` stopped during collection:

```text
ModuleNotFoundError: No module named 'fastapi'
```

`npm run build` stopped before invoking Next.js:

```text
'next' is not recognized as an internal or external command,
operable program or batch file.
```

### Docker baseline at `1589168` in detached worktree

The worktree was created separately at `1589168` (`../beyond-baseline-1589168`) and not modified except for the single temporary longer-timeout Dockerfile edit described below.

`docker compose build` failed in the API image while resolving the pinned runtime requirements:

```text
ERROR: Could not find a version that satisfies the requirement pydantic-core==2.27.2 (from pydantic) (from versions: none)
ERROR: No matching distribution found for pydantic-core==2.27.2
failed to solve: process "/bin/sh -c pip install --no-cache-dir -r requirements.txt" did not complete successfully: exit code: 1
```

`docker compose run --rm api sh -c "pip install pytest httpx && pytest -q"` attempted to build the same missing API image and failed at the same `pydantic-core==2.27.2` dependency-resolution step. Pytest was not reached.

The requested one-time retry added `ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10` to the detached worktree's API Dockerfile, ran `docker compose build api` once, then reverted the temporary edit. The longer timeout allowed wheel downloads to complete, but the build failed at pip's requirements hash verification (`pydantic-core`: expected `ac9dfa18ff2a67b09b372d5db8743c27966abf0e5344c555d86cc7199f7ad83a`, got `dec3a4e18948720644ab2d03882ae2d810f458566e136c3a6a1c6deeab4d39b9`). The temporary edit is reverted and the baseline worktree is clean. No further Docker build was attempted.

Docker build blocked by local network timeouts to PyPI: the initial baseline attempts failed during package resolution/download. The one permitted longer-timeout retry then exposed the hash mismatch above. The feature branch's Docker build and Docker test command were not verified locally and must be run by the reviewer.

Per follow-up instruction, Docker Compose builds/tests on `feat/worlds` were skipped after the retry failed. The lockfile-based frontend Dockerfile, dev requirements test command, and default-off Compose build arguments are committed for reviewer verification.

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
................                                                         [100%]
16 passed, 6 warnings in 12.01s
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
✓ lib/world/world.test.ts (10 tests)
Test Files  1 passed (1)
Tests  10 passed (10)
✓ Compiled successfully
✓ Generating static pages (4/4)
○  (Static) prerendered as static content
```

Command: `npm run validate:world-assets`

```text
World configs and 20 environment placeholder layers validated.
```

The npm audit findings are from the existing pinned dependency tree, including the existing Next.js 15.1.4 version; no dependency was added except Vitest and no broad dependency upgrade was made.

## Acceptance coverage map (`05-acceptance-tests.md`)

| Acceptance item | Test or status |
| --- | --- |
| Config rejects duplicate room IDs | `test_world_loader_rejects_duplicate_room_ids` |
| Config rejects duplicate collider IDs, missing destination spawns, invalid shapes, and out-of-bounds anchors | `test_world_validator_rejects_duplicate_ids_missing_destinations_and_bad_geometry` |
| Spawn, interaction anchor, seat, and portal-trigger overlap validation | `test_world_validator_rejects_overlapping_spawns_anchors_seats_and_trigger_spawns` |
| Original Plaza spec fails portal-threshold reachability; tuned rooms pass flood-fill | `test_original_room_specs_fail_reachability_validation`, `test_each_portal_has_a_reachable_threshold_and_safe_named_spawn` |
| Eligible user enters Plaza at `south_event_entrance` | `test_spatial_portal_uses_server_destination_and_spawn` |
| Ineligible/expired access closes with existing behavior | Manual — event-close and access expiry |
| NaN, impossible speed, and out-of-bounds movement rejected | `test_production_socket_rejects_room_tabs_and_remote_movement` |
| Infinity and direct collider-penetration requests rejected | Manual — WebSocket movement probes |
| Swept movement cannot tunnel through a 32-unit wall | `test_world_config_endpoint_and_authoritative_geometry`, frontend `does not tunnel through a thin wall` |
| Valid diagonal movement accepted | `test_valid_diagonal_movement_is_accepted` |
| Portal outside trigger rejected | `test_production_socket_rejects_room_tabs_and_remote_movement` |
| Every configured portal has a reachable threshold and named safe destination spawn | `test_each_portal_has_a_reachable_threshold_and_safe_named_spawn`; actual travel through every portal remains Manual |
| Presence is event-scoped and room-scoped | `test_room_transition_is_event_scoped`, `test_nearby_chat_remains_private_proximity_and_block_gated` |
| Block hides participant in the next snapshot | `test_nearby_chat_remains_private_proximity_and_block_gated` |
| Nearby private chat succeeds inside 280 and fails outside | `test_nearby_chat_remains_private_proximity_and_block_gated` |
| Reconnect gets safe spawn and does not expose another event | Manual — disconnect/reconnect with two events |
| World-to-screen and screen-to-world round trip | frontend `round trips screen and world positions through the contain transform` |
| Letterboxing in wide and tall viewports | frontend `letterboxes wide and tall viewports without cropping the canonical world` |
| Nearest interaction sorts by priority, then distance | frontend `selects by priority first, then distance within the same priority` |
| Layer order is stable | frontend `orders layers by z while preserving stable order for equal z values` |
| Reduced motion disables optional movement animation | frontend `keeps reduced-motion CSS from running optional movement animation` |
| Revision mismatch refetches once and unresolved mismatch is recoverable | frontend `refetches a changed revision once and verifies the requested room`; `returns a recoverable error when one refresh cannot resolve the mismatch` |
| `worldDebug=1` enables the overlay at runtime without rebuild | frontend `enables the geometry overlay from the runtime query string` |
| For each room: both clients see identical art and each other | Manual — Plaza, Café, Garden, Arcade, Idea Lab |
| For each room: keyboard/touch walking and stop behavior | Manual — Plaza, Café, Garden, Arcade, Idea Lab |
| For each room: labels readable and within playfield | Manual — Plaza, Café, Garden, Arcade, Idea Lab |
| For each room: major obstacles block from each approach | Manual — Plaza, Café, Garden, Arcade, Idea Lab |
| For each room: narrow passages remain traversable | Manual — Plaza, Café, Garden, Arcade, Idea Lab |
| For each room: nearby list/chat radius and keyboard focus/interaction prompts | Manual — two-client room pass |
| For each room: foreground art covers occupants correctly | Manual — visual pass |
| Every portal: correct prompt, one transition, arrival spawn/facing, origin presence removal, and correct Plaza return point | Manual — all eight portal trips |
| Plaza fountain ring, four clear paths, kiosk, and real-only event boards | Manual — Plaza pass |
| Café main aisle, table seat clearance, intended chat groupings | Automated geometry validation for seats; Manual — Café pass |
| Garden water/plant blocking, both decks/rails, no loop dead ends | Automated bridge traversal/rail tests; Manual — full Garden loop |
| Arcade blockers and honest placeholder panels; no flashing/reduced-motion view | Manual — Arcade pass; reduced-motion CSS unit test |
| Idea Lab blockers, own-project privacy, and read-only whiteboard | Viewer-only persona endpoint is wired; Manual — two-client privacy and panel pass |
| Responsive 1440×900, 1280×720, ~390×844, and 200% zoom | Manual — browser viewports |
| Slow network, failed optional layer, WebSocket reconnect, event start close | Layer fallback implemented; Manual — resilience pass |
| Screenshots of five rooms and Plaza debug overlay | Manual — save to `docs/worlds-screenshots/` |

### Plaza kiosk callback verification

`frontend/components/world/WorldView.tsx`: `if(action.type==='open_existing_view'&&action.view==='people'){onOpenPeople();return}`. The page supplies the existing `openPeople` callback, preserving the app's People view behavior.

### Manual visual checks

The API was started with `DATABASE_URL=sqlite:///C:/Users/VIR/Documents/ChatGPT/Devday/beyond-worlds-demo.sqlite` using single-worker Uvicorn on port 8000, and `py -3.12 seed_demo.py` created the fictional demo on that clean SQLite database. The frontend dev server is running on port 3000. No Playwright screenshot matrix was captured; Vitest remains the only added test dependency. Two-account visual verification at 1440×900 and ~390px, including the debug overlay screenshot, is waiting for the user to sign in as demo Alex and demo Devon in separate browser sessions. Automated server tests cover portal thresholds and safe destinations, both bridge crossings/rails, movement validation, event-scoped presence, nearby private chat, and block hiding on the next snapshot.
