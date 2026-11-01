export type Point = { x: number; y: number };
export type WorldAction = { type: string; view?: string; panel?: string; activity?: string; seatGroup?: string };
export type WorldRoom = {
  id: string; name: string; bounds: { x: number; y: number; width: number; height: number };
  layers: { id: string; src: string; z: number }[];
  spawns: { id: string; x: number; y: number; facing: string }[];
  colliders: any[]; portals: { id: string; trigger: any; destination: { roomId: string; spawnId: string }; label: string; priority: number }[];
  interactions: { id: string; anchor: Point; radius: number; priority: number; action: WorldAction; label: string }[];
};
export type WorldsConfig = { revision: string; coordinateSystem: { width: number; height: number; participantRadius: number; walkSpeedPerSecond: number; chatRadius: number }; rooms: WorldRoom[] };
