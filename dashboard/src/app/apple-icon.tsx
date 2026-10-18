import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

// The icon.svg mark on its 16-unit grid. iOS rounds the corners itself.
const UNIT = size.width / 16;

function Bar({ x, width, color }: { x: number; width: number; color: string }) {
  return (
    <div
      style={{
        position: "absolute",
        left: x * UNIT,
        top: 3 * UNIT,
        width: width * UNIT,
        height: 10 * UNIT,
        background: color,
      }}
    />
  );
}

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ display: "flex", position: "relative", width: "100%", height: "100%", background: "#1c2330" }}>
        <Bar x={3} width={3} color="#d9dcdf" />
        <Bar x={10} width={3} color="#d9dcdf" />
        <Bar x={7} width={2} color="#f2c230" />
      </div>
    ),
    size,
  );
}
