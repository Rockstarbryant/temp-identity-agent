import type { Metadata } from "next";
import "./globals.css";
import NavBar from "@/components/NavBar";

export const metadata: Metadata = {
  title: "Temporary Identity Agent",
  description: "Create a temporary account without using your personal email.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <NavBar />
        <main className="mx-auto max-w-3xl px-4 py-6 pb-28 md:py-8 md:pb-8">{children}</main>
      </body>
    </html>
  );
}
