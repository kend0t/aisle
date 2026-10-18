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

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          width: "100%",
          height: "100%",
          padding: "0 96px",
          background: "#fafbfb",
          color: "#1c2330",
          fontFamily: "Sofia Sans",
        }}
      >
        {/*
          Same proportions as Wordmark.module.css. Satori has no baseline alignment for a
          box, so the bar sits on the line's bottom and is raised to the baseline: Sofia Sans
          descends 0.3em, less 0.1em of half-leading at line-height 1.
        */}
        <div style={{ display: "flex", alignItems: "flex-end", fontSize: 200, fontWeight: 800, letterSpacing: "-0.01em", lineHeight: 1 }}>
          A
          <div style={{ width: "0.15em", height: "0.655em", margin: "0 0.066em 0.2em", background: "#f2c230" }} />
          sle
        </div>
        <div style={{ display: "flex", flexDirection: "column", marginTop: 48, fontSize: 40, fontWeight: 400, lineHeight: 1.3, color: "#47505e" }}>
          <div>Shelf-level shopper analytics. Overhead clips read by Gemini show what shoppers pick up, put back, and why.</div>
          <div style={{ marginTop: 24, fontSize: 32, color: "#626b78" }}>Built for the Google AI Builder Cup</div>
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
