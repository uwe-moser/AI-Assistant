import type { Metadata } from "next";
import { Fraunces, Instrument_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  axes: ["opsz"],
  display: "swap",
});

const instrument = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ApexFlow — Multi-agent orchestration, on your machine.",
  description:
    "Eight specialists. One orchestrator. A hierarchical multi-agent assistant built on LangGraph, Playwright and ChromaDB.",
  openGraph: {
    title: "ApexFlow — Multi-agent orchestration",
    description: "Eight specialists. One orchestrator. Zero compromise.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${instrument.variable} ${jetbrains.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
