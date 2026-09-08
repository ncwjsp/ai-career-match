import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Career Match",
  description: "One resume. Opportunities that understand your experience.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-10 sm:px-12">
          <header className="flex items-center justify-between border-b border-emerald-950/15 pb-6">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              AI Career Match<span className="text-emerald-600">.</span>
            </Link>
            <span className="rounded-full border border-emerald-950/20 px-3 py-1 text-xs">
              Project preview
            </span>
          </header>
          <main className="flex-1 py-10">{children}</main>
          <footer className="border-t border-emerald-950/15 pt-6 text-xs text-emerald-950/60">
            Assumption University · NLP Project 2026
          </footer>
        </div>
      </body>
    </html>
  );
}
