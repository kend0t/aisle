import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const alt = "AIsle: shelf-level shopper analytics";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Satori takes static fonts only, so the brand weights are committed next to this file.
// Read at module scope so the image prerenders at build time.
const fontDir = join(process.cwd(), "src/app/_brand");
const [regular, heavy] = await Promise.all([
  readFile(join(fontDir, "SofiaSans-400.ttf")),
  readFile(join(fontDir, "SofiaSans-800.ttf")),
]);

// The icon.svg mark on its 16-unit grid, drawn large on the right.
const MARK = 320;
const UNIT = MARK / 16;

// Same tile and line as the floor grid behind the shelf funnel: 48px squares in ink at 6%.
// Satori draws no repeating gradients, so each line is its own box.
const TILE = 48;
const GRID_LINE = "rgba(28, 35, 48, 0.06)";
const columns = Array.from({ length: Math.ceil(size.width / TILE) }, (_, i) => i * TILE);
const rows = Array.from({ length: Math.ceil(size.height / TILE) }, (_, i) => i * TILE);

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

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          position: "relative",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          height: "100%",
          padding: "0 96px",
          background: "#fafbfb",
          color: "#1c2330",
          fontFamily: "Sofia Sans",
        }}
      >
        {columns.map((x) => (
          <div key={`x${x}`} style={{ position: "absolute", left: x, top: 0, width: 1, height: "100%", background: GRID_LINE }} />
        ))}
        {rows.map((y) => (
          <div key={`y${y}`} style={{ position: "absolute", left: 0, top: y, width: "100%", height: 1, background: GRID_LINE }} />
        ))}
        {/* Fades the grid out toward the bottom, as on the page. */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: "linear-gradient(to bottom, rgba(250, 251, 251, 0) 45%, #fafbfb)",
          }}
        />

        <div style={{ display: "flex", flexDirection: "column", width: 660 }}>
          {/*
            Same proportions as Wordmark.module.css. Satori has no baseline alignment for a
            box, so the bar sits on the line's bottom and is raised to the baseline: Sofia Sans
            descends 0.3em, less 0.1em of half-leading at line-height 1.
          */}
          <div style={{ display: "flex", alignItems: "flex-end", fontSize: 168, fontWeight: 800, letterSpacing: "-0.01em", lineHeight: 1 }}>
            A
            <div style={{ width: "0.15em", height: "0.655em", margin: "0 0.066em 0.2em", background: "#f2c230" }} />
            sle
          </div>
          <div style={{ marginTop: 40, fontSize: 46, fontWeight: 800, lineHeight: 1.15 }}>Shelf-level shopper analytics</div>
          <div style={{ marginTop: 16, fontSize: 32, lineHeight: 1.3, color: "#47505e" }}>
            Overhead clips read by Gemini show what shoppers pick up, put back, and why.
          </div>
          <div style={{ marginTop: 40, fontSize: 26, color: "#626b78" }}>Built for the Google AI Builder Cup</div>
        </div>

        <div
          style={{
            display: "flex",
            position: "relative",
            width: MARK,
            height: MARK,
            borderRadius: 3.5 * UNIT,
            background: "#1c2330",
          }}
        >
          <Bar x={3} width={3} color="#d9dcdf" />
          <Bar x={10} width={3} color="#d9dcdf" />
          <Bar x={7} width={2} color="#f2c230" />
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Sofia Sans", data: regular, weight: 400, style: "normal" },
        { name: "Sofia Sans", data: heavy, weight: 800, style: "normal" },
      ],
    },
  );
}
