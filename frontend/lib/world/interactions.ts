import type { Point } from './types';

export type Interactable = { anchor: Point; radius: number; priority: number };

export function selectNearestInteraction<T extends Interactable>(items: T[], point: Point): T | undefined {
  return items
    .filter((item) => Math.hypot(item.anchor.x - point.x, item.anchor.y - point.y) <= item.radius)
    .sort((a, b) => b.priority - a.priority || Math.hypot(a.anchor.x - point.x, a.anchor.y - point.y) - Math.hypot(b.anchor.x - point.x, b.anchor.y - point.y))[0];
}

export function orderWorldLayers<T extends { z: number }>(layers: T[]): T[] {
  return layers.map((layer, index) => ({ layer, index }))
    .sort((a, b) => a.layer.z - b.layer.z || a.index - b.index)
    .map(({ layer }) => layer);
}

export function isWorldDebugQuery(search: string): boolean {
  return new URLSearchParams(search).get('worldDebug') === '1';
}
