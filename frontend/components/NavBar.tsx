"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated, logout } from "@/lib/api";
import { UserRound, LogOut, ShieldCheck } from "lucide-react";

export default function NavBar() {
  const [authed, setAuthed] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, [pathname]);

  async function handleLogout() {
    await logout();
    setAuthed(false);
    router.push("/login");
  }

  return (
    <header className="border-b border-black/10 bg-white">
      <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold text-ink">
          <ShieldCheck className="h-5 w-5 text-accent" />
          Temp Identity Agent
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          {authed ? (
            <>
              <Link href="/dashboard" className="hover:text-accent">Dashboard</Link>
              <Link href="/accounts" className="hover:text-accent">Vault</Link>
              <Link href="/settings" className="hover:text-accent">Settings</Link>
              <button onClick={handleLogout} className="flex items-center gap-1 text-red-600 hover:text-red-700">
                <LogOut className="h-4 w-4" /> Logout
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="hover:text-accent">Login</Link>
              <Link href="/register" className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-white hover:bg-accent/90">
                <UserRound className="h-4 w-4" /> Sign up
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
