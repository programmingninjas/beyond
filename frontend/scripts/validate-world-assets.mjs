import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
const backendWorlds = path.resolve(frontend, '..', 'backend', 'worlds');
const publicWorlds = path.join(frontend, 'public', 'worlds');
const requiredRooms = new Set(['plaza', 'cafe', 'garden', 'arcade', 'lab']);
const rooms = new Map();
const fail = (message) => { throw new Error(message); };

for (const id of requiredRooms) {
  const config = JSON.parse(await readFile(path.join(backendWorlds, `${id}.json`), 'utf8'));
  if (config.room?.id !== id) fail(`${id}: config room ID mismatch`);
  rooms.set(id, config.room);
  const manifest = JSON.parse(await readFile(path.join(publicWorlds, id, 'manifest.json'), 'utf8'));
  if (manifest.roomId !== id || manifest.coordinateSpace?.[0] !== 1920 || manifest.coordinateSpace?.[1] !== 1080) fail(`${id}: manifest coordinates or room ID mismatch`);
  const layerIds = new Set();
  for (const layer of manifest.layers ?? []) {
    if (layerIds.has(layer.id)) fail(`${id}: duplicate layer ID ${layer.id}`);
    layerIds.add(layer.id);
    if (layer.placeholder !== true || layer.width !== 1920 || layer.height !== 1080) fail(`${id}/${layer.id}: expected a 1920x1080 placeholder layer`);
    const bytes = await readFile(path.join(publicWorlds, id, layer.file));
    const digest = createHash('sha256').update(bytes).digest('hex');
    if (digest !== layer.sha256) fail(`${id}/${layer.id}: SHA-256 does not match manifest`);
    const svg = bytes.toString('utf8');
    if (!svg.includes('width="1920" height="1080" viewBox="0 0 1920 1080"')) fail(`${id}/${layer.id}: invalid canonical dimensions`);
    if (/<(?:text|image)\b/i.test(svg)) fail(`${id}/${layer.id}: baked text or raster reference art is not allowed`);
  }
  if (layerIds.size !== 4 || !['background', 'ground', 'midground', 'foreground'].every((id) => layerIds.has(id))) fail(`${id}: missing one or more swappable environment layers`);
  if (JSON.stringify(config.room.layers.map((layer) => layer.id).sort()) !== JSON.stringify([...layerIds].sort())) fail(`${id}: room config and manifest layers differ`);
}

for (const [id, room] of rooms) {
  for (const portal of room.portals ?? []) {
    const dest = portal.destination;
    if (!rooms.has(dest.roomId) || !rooms.get(dest.roomId).spawns.some((spawn) => spawn.id === dest.spawnId)) fail(`${id}/${portal.id}: destination spawn does not exist`);
    if (id === 'plaza' && dest.roomId !== 'plaza') continue;
    if (id !== 'plaza' && dest.roomId !== 'plaza') fail(`${id}/${portal.id}: rooms must return to the plaza hub`);
  }
  for (const seat of room.seats ?? []) if (!seat.id || !Number.isFinite(seat.x) || !Number.isFinite(seat.y) || !seat.facing) fail(`${id}: malformed seat entry`);
}
for (const id of requiredRooms) if (id !== 'plaza' && !rooms.get(id).portals.some((portal) => portal.destination.roomId === 'plaza')) fail(`${id}: missing return portal`);
const plazaDestinations = new Set(rooms.get('plaza').portals.map((portal) => portal.destination.roomId));
for (const id of ['cafe', 'garden', 'arcade', 'lab']) if (!plazaDestinations.has(id)) fail(`plaza: missing portal to ${id}`);
console.log('World configs and 20 environment placeholder layers validated.');
