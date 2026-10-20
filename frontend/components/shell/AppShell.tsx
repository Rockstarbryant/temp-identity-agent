"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity, Home, KeyRound, LogOut, Mail, PanelLeftClose, PanelLeftOpen, Settings, ShieldCheck,
} from "lucide-react";
import { isAuthenticated, logout } from "@/lib/api";
import { stopNotifications } from "@/lib/notifications";
import NotificationBell from "@/components/NotificationBell";
import { buttonClass } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Home;
  match: (p: string) => boolean;
}

const NAV: NavItem[] = [
  { href: "/", label: "Home", icon: Home, match: (p) => p === "/" },
  { href: "/dashboard", label: "Activity", icon: Activity, match: (p) => p.startsWith("/dashboard") || p.startsWith("/jobs") },
  { href: "/mailboxes", label: "Mailboxes", icon: Mail, match: (p) => p.startsWith("/mailboxes") },
  { href: "/accounts", label: "Identity Vault", icon: KeyRound, match: (p) => p.startsWith("/accounts") },
  { href: "/settings", label: "Settings", icon: Settings, match: (p) => p.startsWith("/settings") },
];

const AUTH_ROUTES = ["/login", "/register"];
const COLLAPSE_KEY = "tia_sidebar_collapsed";

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2 rounded-md font-semibold text-ink" aria-label="Temp Identity Agent, home">
      <ShieldCheck className="h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
      {!compact && <span className="whitespace-nowrap text-sm">Temp Identity Agent</span>}
    </Link>
  );
}

/**
 * The application frame: collapsible sidebar and header on desktop, header and bottom
 * navigation on phones. Signed-out visitors (and the login / register screens) get a
 * minimal header instead, so no navigation to protected pages is shown without a session.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const [authed, setAuthed] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, [pathname]);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      /* storage unavailable: default to expanded */
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((c) => {
      try {
        window.localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !c;
    });
  }

  async function handleLogout() {
    try {
      await logout();
    } finally {
      stopNotifications();
      setAuthed(false);
      router.push("/login");
    }
  }

  const bare = !authed || AUTH_ROUTES.includes(pathname);

  if (bare) {
    return (
      <div className="min-h-dvh">
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 md:px-8">
            <Brand />
            {!AUTH_ROUTES.includes(pathname) && (
              <nav aria-label="Account" className="flex items-center gap-2">
                <Link href="/login" className={buttonClass("ghost", "sm")}>Log in</Link>
                <Link href="/register" className={buttonClass("primary", "sm")}>Sign up</Link>
              </nav>
            )}
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-5xl px-4 py-8 md:px-8 md:py-12">{children}</main>
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[70] focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:shadow-sm"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line bg-surface transition-[width] md:flex",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <div className={cn("flex h-14 items-center border-b border-line", collapsed ? "justify-center" : "px-4")}>
          <Brand compact={collapsed} />
        </div>
        <nav aria-label="Primary" className="flex-1 space-y-1 p-2">
          {NAV.map(({ href, label, icon: Icon, match }) => {
            const active = match(pathname);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                title={collapsed ? label : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  collapsed && "justify-center px-0",
                  active ? "bg-accent-soft font-medium text-accent-strong" : "text-muted hover:bg-subtle hover:text-ink",
                )}
              >
                <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                <span className={collapsed ? "sr-only" : ""}>{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-line p-2">
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-pressed={collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted transition-colors hover:bg-subtle hover:text-ink",
              collapsed && "justify-center px-0",
            )}
          >
            {collapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" aria-hidden="true" /> : <PanelLeftClose className="h-[18px] w-[18px]" aria-hidden="true" />}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      <div className={cn("transition-[padding]", collapsed ? "md:pl-16" : "md:pl-60")}>
        <header
          className="sticky top-0 z-20 border-b border-line bg-surface"
          style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
        >
          <div className="flex h-14 items-center justify-between gap-2 px-4 md:px-8">
            <div className="md:hidden"><Brand /></div>
            <div className="hidden md:block" />
            <div className="flex items-center gap-1">
              <NotificationBell />
              <button
                type="button"
                onClick={handleLogout}
                aria-label="Log out"
                className="inline-flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm text-muted transition-colors hover:bg-danger-soft hover:text-danger"
              >
                <LogOut className="h-[18px] w-[18px]" aria-hidden="true" />
                <span className="hidden sm:inline">Log out</span>
              </button>
            </div>
          </div>
        </header>

        <main id="main" className="mx-auto w-full max-w-5xl px-4 py-6 pb-28 md:px-8 md:py-8 md:pb-10">
          {children}
        </main>
      </div>

      {/* Phone bottom navigation */}
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        <ul className="grid grid-cols-5">
          {NAV.map(({ href, label, icon: Icon, match }) => {
            const active = match(pathname);
            const short = label === "Identity Vault" ? "Vault" : label;
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  aria-label={label}
                  className={cn(
                    "flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[11px]",
                    active ? "font-medium text-accent-strong" : "text-muted",
                  )}
                >
                  <Icon className={cn("h-5 w-5", active && "stroke-[2.25]")} aria-hidden="true" />
                  <span>{short}</span>
                  {active && <span className="sr-only">(current page)</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
