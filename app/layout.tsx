/* eslint-disable @next/next/no-page-custom-font -- Material Symbols is an icon glyph stylesheet; text fonts use next/font. */
import type { Metadata } from "next";
import { Oswald, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const oswald = Oswald({
  variable: "--font-oswald",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const hankenGrotesk = Hanken_Grotesk({
  variable: "--font-hanken",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: "Auto-Gaffer | World Cup Live",
  description:
    "AI-powered autonomous fantasy football manager for the 2026 FIFA World Cup. Built on Injective with x402, CCTP, Agent Skills, and MCP.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${oswald.variable} ${hankenGrotesk.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased min-h-screen flex flex-col overflow-hidden">
        {children}
      </body>
    </html>
  );
}
