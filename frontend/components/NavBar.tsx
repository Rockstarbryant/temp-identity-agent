"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated, logout } from "@/lib/api";
import NotificationBell from "@/components/NotificationBell";
import { stopNotifications } from "@/lib/notifications";
import { KeyRound, ListChecks, LogOut, Plus, Settings, ShieldCheck, UserRound } from "lucide-react";

const ITEMS = [
  { href: "/", label: "New", icon: Plus, match: (p: string) => p === "/" },
  { href: "/dashboard", label: "Jobs", icon: ListChecks, match: (p: string) => p.startsWith("/dashboard") || p.startsWith("/jobs") },
  { href: "/accounts", label: "Vault", icon: KeyRound, match: (p: string) => p.startsWith("/accounts") },
  { href: "/settings", label: "Settings", icon: Settings, match: (p: string) => p.startsWith("/settings") },
];

export default function NavBar() {
  const [authed, setAuthed] = useState(false);
  const pathname = usePathname() || "/";
  const router = useRouter();

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, [pathname]);

  async function handleLogout() {
    await logout();
    stopNotifications();
    setAuthed(false);
    router.push("/login");
  }

  return (
    <>
      {/* Top bar: brand + (desktop) tabs + account actions. Never wraps. */}
      <header className="sticky top-0 z-30 border-b border-black/10 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center gap-3 px-4">
          <Link href="/" className="flex shrink-0 items-center gap-2 whitespace-nowrap font-semibold text-ink">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <span className="hidden min-[380px]:inline">Temp Identity Agent</span>
            <span className="min-[380px]:hidden">Temp ID</span>
          </Link>

          {authed ? (
            <>
              <nav className="ml-4 hidden flex-1 items-center gap-1 md:flex" aria-label="Main">
                {ITEMS.map(({ href, label, icon: Icon, match }) => {
                  const active = match(pathname);
                  return (
                    <Link
                      key={href}
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                        active ? "bg-accent/10 font-medium text-accent" : "text-black/60 hover:bg-black/5 hover:text-ink"
                      }`}
                    >
                      <Icon className="h-4 w-4" /> {label}
                    </Link>
                  );
                })}
              </nav>
              <div className="ml-auto flex items-center gap-1 md:ml-0">
                <NotificationBell />
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-1 rounded-md px-2.5 py-1.5 text-sm text-black/50 hover:bg-red-50 hover:text-red-600"
                  aria-label="Log out"
                >
                  <LogOut className="h-4 w-4" />
                  <span className="hidden sm:inline">Log out</span>
                </button>
              </div>
            </>
          ) : (
            <nav className="ml-auto flex items-center gap-2 text-sm">
              <Link href="/login" className="rounded-md px-3 py-1.5 text-black/70 hover:bg-black/5">Login</Link>
              <Link href="/register" className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-white hover:bg-accent/90">
                <UserRound className="h-4 w-4" /> Sign up
              </Link>
            </nav>
          )}
        </div>
      </header>

      {/* Phone: fixed bottom tab bar, thumb-reachable. */}
      {authed && (
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-30 border-t border-black/10 bg-white/95 backdrop-blur md:hidden"
          style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
        >
          <ul className="mx-auto grid max-w-3xl grid-cols-4">
            {ITEMS.map(({ href, label, icon: Icon, match }) => {
              const active = match(pathname);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`flex flex-col items-center gap-0.5 py-2 text-[11px] ${
                      active ? "font-medium text-accent" : "text-black/50"
                    }`}
                  >
                    <Icon className={`h-5 w-5 ${active ? "stroke-[2.4]" : ""}`} />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </>
  );
}
