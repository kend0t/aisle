import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import Providers from "./providers";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--font-archivo",
});

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
    <html lang="en" className={archivo.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
