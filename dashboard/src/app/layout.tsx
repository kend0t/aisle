import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIsle | Physical Retail Behavioral Intelligence",
  description: "Next-generation retail analytics powered by Google Gemini multimodal video vision and Google Cloud.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
