// Zone outlines in camera pixel space (920 x 680 MERL overhead frame).
// Source of truth: camera_node/config.py (EdgeConfig.zones). Keep the two in sync.

export const FRAME_WIDTH = 920;
export const FRAME_HEIGHT = 680;

export interface ZoneShape {
  id: string;
  name: string;
  polygon: [number, number][];
}

export const ZONES: ZoneShape[] = [
  {
    id: "left_bay_cereal",
    name: "Left bay, cereal",
    polygon: [
      [180, 250],
      [550, 250],
      [550, 520],
      [180, 520],
    ],
  },
  {
    id: "right_bay_snacks",
    name: "Right bay, snacks",
    polygon: [
      [550, 250],
      [890, 250],
      [890, 520],
      [550, 520],
    ],
  },
];

export function zoneCentroid(zone: ZoneShape): [number, number] {
  const xs = zone.polygon.map(([x]) => x);
  const ys = zone.polygon.map(([, y]) => y);
  return [
    xs.reduce((a, b) => a + b, 0) / xs.length,
    ys.reduce((a, b) => a + b, 0) / ys.length,
  ];
}
