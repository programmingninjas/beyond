import { describe, expect, it } from 'vitest';
import { containViewport, screenToWorld, worldToScreen } from './coordinates';
import { sweepMove } from './collision';

describe('canonical world coordinates', () => {
  it('contains a 1920x1080 world in a letterboxed viewport', () => {
    const viewport = containViewport(1000, 1000);
    expect(viewport.scale).toBeCloseTo(1000 / 1920);
    expect(viewport.top).toBeCloseTo((1000 - 1080 * viewport.scale) / 2);
    expect(viewport.left).toBeCloseTo(0, 8);
  });

  it('round trips screen and world positions through the contain transform', () => {
    const viewport = containViewport(1280, 720);
    const point = { x: 1520, y: 780 };
    expect(screenToWorld(worldToScreen(point, viewport), viewport)).toEqual(point);
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
