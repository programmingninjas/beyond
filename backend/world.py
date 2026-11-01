"""Canonical, server-owned world geometry and movement rules."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

WORLD_DIR = Path(__file__).with_name('worlds')
WIDTH, HEIGHT = 1920.0, 1080.0
RADIUS, WALK_SPEED, CHAT_RADIUS = 28.0, 250.0, 280.0
REVISION = 'worlds-v1'
ROOMS: dict[str, dict[str, Any]] = {}


def _inside_aabb(x: float, y: float, shape: dict, radius: float = 0) -> bool:
    return (shape['x'] - radius <= x <= shape['x'] + shape['width'] + radius and
            shape['y'] - radius <= y <= shape['y'] + shape['height'] + radius)


def _point_segment_distance(x: float, y: float, a: list[float], b: list[float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((x-a[0])*dx + (y-a[1])*dy) / denom)) if denom else 0.0
    return math.hypot(x - (a[0] + t*dx), y - (a[1] + t*dy))


def _inside_polygon(x: float, y: float, points: list[list[float]]) -> bool:
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj-xi) * (y-yi) / ((yj-yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def shape_contains(shape: dict, x: float, y: float, radius: float = 0) -> bool:
    kind = shape.get('shape')
    if kind == 'aabb':
        # Rounded expansion makes the participant's circular footprint collide.
        px = max(shape['x'], min(x, shape['x'] + shape['width']))
        py = max(shape['y'], min(y, shape['y'] + shape['height']))
        return math.hypot(x-px, y-py) < radius if radius else _inside_aabb(x, y, shape)
    if kind == 'circle':
        return math.hypot(x-shape['x'], y-shape['y']) < shape['radius'] + radius
    if kind == 'polygon':
        points = shape['points']
        return _inside_polygon(x, y, points) or (radius > 0 and any(
            _point_segment_distance(x, y, points[i], points[(i+1) % len(points)]) < radius
            for i in range(len(points))))
    return False


def in_bounds(room: dict, x: float, y: float, radius: float = RADIUS) -> bool:
    b = room['bounds']
    return b['x'] + radius <= x <= b['x'] + b['width'] - radius and b['y'] + radius <= y <= b['y'] + b['height'] - radius


def on_walkable(room: dict, x: float, y: float) -> bool:
    polygons = room.get('walkablePolygons', [])
    if not polygons: return True
    bridge = [p for p in polygons if 'bridge' in p['id']]
    if any(_inside_polygon(x, y, p['points']) for p in bridge): return True
    floor = [p for p in polygons if 'bridge' not in p['id']]
    return any(_inside_polygon(x, y, p['points']) for p in floor)


def blocked(room: dict, x: float, y: float, radius: float = RADIUS) -> bool:
    if not in_bounds(room, x, y, radius) or not on_walkable(room, x, y): return True
    bridge = any('bridge' in p['id'] and _inside_polygon(x, y, p['points']) for p in room.get('walkablePolygons', []))
    return any(shape_contains(c, x, y, radius) for c in room.get('colliders', []) if not (bridge and c['id'] == 'central-pond'))


def safe_spawn(room: dict, spawn_id: str) -> dict:
    spawn = next((s for s in room['spawns'] if s['id'] == spawn_id), None)
    if not spawn or blocked(room, spawn['x'], spawn['y']):
        spawn = next(s for s in room['spawns'] if s['id'] == 'default')
    return spawn


def swept_move(room: dict, old: tuple[float, float], proposed: tuple[float, float]) -> tuple[float, float]:
    """Move in small bounded steps; return the last safe position (no tunneling)."""
    x0, y0 = old
    dx, dy = proposed[0] - x0, proposed[1] - y0
    distance = math.hypot(dx, dy)
    steps = max(1, math.ceil(distance / 6.0))
    x, y = x0, y0
    for i in range(1, steps + 1):
        nx, ny = x0 + dx * i / steps, y0 + dy * i / steps
        if blocked(room, nx, ny):
            # Axis resolution gives basic wall sliding.
            if not blocked(room, nx, y):
                x = nx
            elif not blocked(room, x, ny):
                y = ny
            break
        x, y = nx, ny
    return x, y


def _validate_room(room: dict, all_rooms: dict[str, dict]) -> None:
    rid = room.get('id')
    if not isinstance(rid, str) or not rid:
        raise ValueError('room requires an id')
    bounds = room.get('bounds', {})
    if any(not isinstance(bounds.get(k), (int, float)) or bounds[k] <= 0 for k in ('width', 'height')) or any(not isinstance(bounds.get(k), (int, float)) or bounds[k] < 0 for k in ('x', 'y')) or bounds['x'] + bounds['width'] > WIDTH or bounds['y'] + bounds['height'] > HEIGHT:
        raise ValueError(f'{rid}: invalid bounds')
    for key in ('spawns', 'colliders', 'portals', 'interactions'):
        ids = [item.get('id') for item in room.get(key, [])]
        if len(ids) != len(set(ids)):
            raise ValueError(f'{rid}: duplicate {key} id')
    object_ids = [item.get('id') for key in ('colliders','portals','interactions') for item in room.get(key, [])]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError(f'{rid}: duplicate object id')
    spawn_ids = {s['id'] for s in room.get('spawns', [])}
    if 'default' not in spawn_ids:
        raise ValueError(f'{rid}: missing default spawn')
    for spawn in room['spawns']:
        if not in_bounds(room, spawn['x'], spawn['y'], 56) or blocked(room, spawn['x'], spawn['y']) or any(shape_contains(p['trigger'], spawn['x'], spawn['y']) for p in room.get('portals', [])):
            raise ValueError(f"{rid}: unsafe spawn {spawn['id']}")
    for shape in room.get('colliders', []) + [p['trigger'] for p in room.get('portals', [])]:
        kind = shape.get('shape')
        if kind == 'aabb':
            valid = all(isinstance(shape.get(k), (int,float)) for k in ('x','y','width','height')) and shape['x'] >= 0 and shape['y'] >= 0 and shape['width'] > 0 and shape['height'] > 0 and shape['x']+shape['width'] <= WIDTH and shape['y']+shape['height'] <= HEIGHT
        elif kind == 'circle':
            valid = all(isinstance(shape.get(k), (int,float)) for k in ('x','y','radius')) and shape['radius'] > 0 and shape['radius'] <= shape['x'] <= WIDTH-shape['radius'] and shape['radius'] <= shape['y'] <= HEIGHT-shape['radius']
        elif kind == 'polygon':
            points = shape.get('points', [])
            valid = len(points) >= 3 and all(len(p)==2 and 0 <= p[0] <= WIDTH and 0 <= p[1] <= HEIGHT for p in points)
        else:
            valid = False
        if not valid: raise ValueError(f"{rid}: invalid {kind or 'unknown'} geometry")
    for polygon in room.get('walkablePolygons', []):
        points = polygon.get('points', [])
        if len(points) < 3 or any(len(p)!=2 or not 0 <= p[0] <= WIDTH or not 0 <= p[1] <= HEIGHT for p in points):
            raise ValueError(f"{rid}: invalid walkable polygon {polygon.get('id')}")
    for portal in room.get('portals', []):
        dest = portal.get('destination', {})
        if dest.get('roomId') not in all_rooms or dest.get('spawnId') not in {s['id'] for s in all_rooms.get(dest.get('roomId'), {}).get('spawns', [])}:
            raise ValueError(f"{rid}: invalid destination for {portal.get('id')}")
    for interaction in room.get('interactions', []):
        a = interaction.get('anchor', {})
        if not (0 <= a.get('x', -1) <= WIDTH and 0 <= a.get('y', -1) <= HEIGHT and interaction.get('radius', 0) > 0):
            raise ValueError(f"{rid}: invalid interaction anchor")


def load_worlds() -> dict[str, dict[str, Any]]:
    loaded = {}
    for path in sorted(WORLD_DIR.glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        room = document['room']
        if document.get('revision') != REVISION:
            raise ValueError(f'{path.name}: world revision must be {REVISION}')
        if room['id'] in loaded:
            raise ValueError(f"duplicate room id {room['id']}")
        loaded[room['id']] = room
    if set(loaded) != {'plaza', 'cafe', 'garden', 'arcade', 'lab'}:
        raise ValueError('world config must contain exactly the five supported rooms')
    for room in loaded.values():
        _validate_room(room, loaded)
    return loaded


def public_worlds() -> dict:
    return {'revision': REVISION, 'coordinateSystem': {'width': WIDTH, 'height': HEIGHT, 'participantRadius': RADIUS, 'walkSpeedPerSecond': WALK_SPEED, 'chatRadius': CHAT_RADIUS}, 'rooms': list(ROOMS.values())}


ROOMS.update(load_worlds())
