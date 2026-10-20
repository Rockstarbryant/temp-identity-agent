import type { Metadata, Viewport } from "next";
import "./globals.css";
import AppShell from "@/components/shell/AppShell";
import { FeedbackProvider } from "@/components/ui/Feedback";
import PwaRegister from "@/components/pwa/PwaRegister";

export const metadata: Metadata = {
  title: "Temp Identity Agent",
  description: "Create a temporary account without using your personal email.",
  applicationName: "Temp Identity Agent",
  icons: { icon: "/icons/192", apple: "/icons/apple-180" },
  appleWebApp: { capable: true, title: "Temp Identity", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
    { media: "(prefers-color-scheme: dark)", color: "#141414" },
  ],
};

// Runs before first paint so a saved Light/Dark choice never flashes the wrong theme. Static text, no user data.
const THEME_SCRIPT = `try{var t=localStorage.getItem("tia_theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-dvh">
        <PwaRegister />
        <FeedbackProvider>
          <AppShell>{children}</AppShell>
        </FeedbackProvider>
      </body>
    </html>
  );
}
