import type { Metadata, Viewport } from "next";
import { Sofia_Sans, Sofia_Sans_Extra_Condensed } from "next/font/google";
import Providers from "./providers";
import "./globals.css";

// Text in Sofia Sans; figures in its extra-condensed cut, like the price on a shelf tag.
const sofiaSans = Sofia_Sans({ subsets: ["latin"], variable: "--font-text" });
const sofiaFigures = Sofia_Sans_Extra_Condensed({ subsets: ["latin"], variable: "--font-figure" });

export const metadata: Metadata = {
  title: "AIsle",
  description:
    "Shelf-level shopper analytics. Overhead clips read by Gemini show what shoppers pick up, put back, and why.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafbfb" },
    { media: "(prefers-color-scheme: dark)", color: "#161a20" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sofiaSans.variable} ${sofiaFigures.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
