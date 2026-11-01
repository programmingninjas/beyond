import type { Point } from './types';
export const WORLD_WIDTH = 1920;
export const WORLD_HEIGHT = 1080;
export type Viewport = { width: number; height: number; scale: number; left: number; top: number };
export function containViewport(width: number, height: number): Viewport {
  const scale = Math.min(width / WORLD_WIDTH, height / WORLD_HEIGHT);
  return { width, height, scale, left: (width - WORLD_WIDTH * scale) / 2, top: (height - WORLD_HEIGHT * scale) / 2 };
}
export function worldToScreen(point: Point, viewport: Viewport): Point {
  return { x: viewport.left + point.x * viewport.scale, y: viewport.top + point.y * viewport.scale };
}
export function screenToWorld(point: Point, viewport: Viewport): Point {
  return { x: (point.x - viewport.left) / viewport.scale, y: (point.y - viewport.top) / viewport.scale };
}
