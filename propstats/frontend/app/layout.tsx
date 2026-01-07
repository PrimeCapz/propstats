import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PropStats - NBA Props Research & Analysis",
  description: "Free NBA player props research tool with historical hit rates, game logs, and trend analysis. Compare lines across sportsbooks.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
