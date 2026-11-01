import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { containViewport, screenToWorld, worldToScreen } from './coordinates';
import { sweepMove } from './collision';
import { refetchWorldConfigOnRevisionMismatch } from './config';
import { isWorldDebugQuery, orderWorldLayers, selectNearestInteraction } from './interactions';

describe('canonical world coordinates', () => {
  it('contains a 1920x1080 world in a letterboxed viewport', () => {
    const viewport = containViewport(1000, 1000);
    expect(viewport.scale).toBeCloseTo(1000 / 1920);
    expect(viewport.top).toBeCloseTo((1000 - 1080 * viewport.scale) / 2);
    expect(viewport.left).toBeCloseTo(0, 8);
  });

  it('letterboxes wide and tall viewports without cropping the canonical world', () => {
    const wide = containViewport(2560, 900);
    expect(wide.scale).toBeCloseTo(900 / 1080);
    expect(wide.left).toBeGreaterThan(0);
    expect(wide.top).toBeCloseTo(0);
    const tall = containViewport(390, 844);
    expect(tall.scale).toBeCloseTo(390 / 1920);
    expect(tall.top).toBeGreaterThan(0);
    expect(tall.left).toBeCloseTo(0);
  });

  it('round trips screen and world positions through the contain transform', () => {
    const viewport = containViewport(1280, 720);
    const point = { x: 1520, y: 780 };
    expect(screenToWorld(worldToScreen(point, viewport), viewport)).toEqual(point);
  });
});

describe('world interaction and layer ordering', () => {
  it('selects by priority first, then distance within the same priority', () => {
    const items = [
      { id: 'near-low', anchor: { x: 2, y: 0 }, radius: 20, priority: 1 },
      { id: 'far-high', anchor: { x: 9, y: 0 }, radius: 20, priority: 2 },
      { id: 'near-high', anchor: { x: 4, y: 0 }, radius: 20, priority: 2 },
    ];
    expect(selectNearestInteraction(items, { x: 0, y: 0 })?.id).toBe('near-high');
  });

  it('orders layers by z while preserving stable order for equal z values', () => {
    const source = [{ id: 'mid', z: 20 }, { id: 'ground-a', z: 10 }, { id: 'ground-b', z: 10 }, { id: 'back', z: 0 }];
    expect(orderWorldLayers(source).map((layer) => layer.id)).toEqual(['back', 'ground-a', 'ground-b', 'mid']);
    expect(source.map((layer) => layer.id)).toEqual(['mid', 'ground-a', 'ground-b', 'back']);
  });

  it('keeps reduced-motion CSS from running optional movement animation', () => {
    const css = readFileSync(resolve(process.cwd(), 'app/world.css'), 'utf8');
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
    expect(css).toMatch(/\.walking[^}]*\{[^}]*animation:\s*none\s*!important/);
  });

  it('enables the geometry overlay from the runtime query string', () => {
    expect(isWorldDebugQuery('?worldDebug=1')).toBe(true);
    expect(isWorldDebugQuery('?worldDebug=0')).toBe(false);
    expect(isWorldDebugQuery('')).toBe(false);
  });
});

describe('world config revision recovery', () => {
  const current = { revision: 'r1', coordinateSystem: { width: 1920, height: 1080, participantRadius: 28, walkSpeedPerSecond: 250, chatRadius: 280 }, rooms: [] };

  it('refetches a changed revision once and verifies the requested room', async () => {
    const refreshed = { ...current, revision: 'r2' };
    const responses = [
      Response.json({ revision: 'r2' }),
      Response.json(refreshed),
      Response.json({ revision: 'r2' }),
    ];
    const fetcher = vi.fn(async () => responses.shift()!);
    await expect(refetchWorldConfigOnRevisionMismatch('http://api', 'plaza', current, fetcher as typeof fetch)).resolves.toEqual(refreshed);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it('returns a recoverable error when one refresh cannot resolve the mismatch', async () => {
    const refreshed = { ...current, revision: 'r2' };
    const responses = [
      Response.json({ revision: 'r2' }),
      Response.json(refreshed),
      Response.json({ revision: 'r3' }),
    ];
    const fetcher = vi.fn(async () => responses.shift()!);
    await expect(refetchWorldConfigOnRevisionMismatch('http://api', 'plaza', current, fetcher as typeof fetch)).rejects.toThrow('World configuration is out of sync. Reload to retry.');
    expect(fetcher).toHaveBeenCalledTimes(3);
  });
});

describe('swept world collision', () => {
  it('does not tunnel through a thin wall', () => {
    const room = { bounds: { x: 0, y: 0, width: 1000, height: 1000 }, colliders: [{ id: 'wall', shape: 'aabb', x: 500, y: 100, width: 32, height: 800 }] };
    const point = sweepMove(room, { x: 200, y: 500 }, { x: 800, y: 500 });
    expect(point.x).toBeLessThanOrEqual(472);
    expect(point.y).toBe(500);
  });
});
