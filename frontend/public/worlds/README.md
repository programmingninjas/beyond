# World environment layers

Each room directory has four aligned, full-frame 1920×1080 SVG placeholder layers: `background`, `ground`, `midground`, and `foreground`. `manifest.json` records layer order, dimensions, and SHA-256 checksums. These are engineering placeholders with no characters, pets, labels, or baked text.

Replace each layer file in place with final art and update its checksum in the manifest. Preserve the filename, room ID, layer ID, dimensions, and shared coordinate origin. Runtime collision and interaction geometry remains server-owned in `backend/worlds/*.json`; image pixels do not define physics. The room compositor reads those layer paths from the public read-only `/worlds` config endpoint.

The SVG placeholders can be regenerated from the canonical backend configs with `python scripts/make_world_placeholders.py` from `frontend/`.

Run `npm run validate:world-assets` from `frontend/` to verify room IDs, portal destinations, layer files, placeholder metadata, dimensions, and checksums.
