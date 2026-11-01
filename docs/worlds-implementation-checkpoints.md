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
