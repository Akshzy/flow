import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Floww",
  description: "Turn customer messages into structured, reviewable orders.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
        <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-500">
          <a
            href="/privacy"
            className="font-medium text-slate-700 underline hover:text-slate-900"
          >
            Privacy Policy
          </a>
        </footer>
      </body>
    </html>
  );
}
