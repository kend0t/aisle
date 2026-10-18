import type { Metadata, Viewport } from "next";
import { Sofia_Sans, Sofia_Sans_Extra_Condensed } from "next/font/google";
import Providers from "./providers";
import "./globals.css";

// Text in Sofia Sans; figures in its extra-condensed cut, like the price on a shelf tag.
const sofiaSans = Sofia_Sans({ subsets: ["latin"], variable: "--font-text" });
const sofiaFigures = Sofia_Sans_Extra_Condensed({ subsets: ["latin"], variable: "--font-figure" });

// Absolute base for the canonical and Open Graph URLs, which crawlers reject when relative.
// Vercel sets its production host on every deploy; elsewhere set NEXT_PUBLIC_SITE_URL.
function siteUrl() {
  if (process.env.NEXT_PUBLIC_SITE_URL) return new URL(process.env.NEXT_PUBLIC_SITE_URL);
  if (process.env.VERCEL_PROJECT_PRODUCTION_URL) return new URL(`https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`);
  return new URL("http://localhost:3000");
}

export const metadata: Metadata = {
  metadataBase: siteUrl(),
  title: "AIsle",
  applicationName: "AIsle",
  description:
    "Shelf-level shopper analytics. Overhead clips read by Gemini show what shoppers pick up, put back, and why.",
  alternates: { canonical: "/" },
  // Title, description and image are inherited from above and from opengraph-image.tsx.
  openGraph: { type: "website", siteName: "AIsle", url: "/", locale: "en_US" },
  twitter: { card: "summary_large_image" },
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
