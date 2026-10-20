"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BookOpen, Menu, ShieldCheck, X } from "lucide-react";
import ThemeToggle from "@/components/ui/ThemeToggle";
import { DOCS_URL, SITE_NAME } from "@/lib/site";
import AuthCta from "./AuthCta";
import { NAV_LINKS } from "./content";
import { BTN_PRIMARY, CONTAINER } from "./ui";

const LINK = "rounded-md px-3 py-2 text-sm text-muted transition-colors hover:text-ink";

export default function MarketingNav() {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  // Escape closes the mobile menu and returns focus to its button.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas">
      <div className={`${CONTAINER} flex h-16 items-center justify-between gap-3`}>
        <Link href="/" className="flex items-center gap-2 rounded-md font-semibold" aria-label={`${SITE_NAME}, home`}>
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-accent-fill text-white">
            <ShieldCheck className="h-[18px] w-[18px]" aria-hidden="true" />
          </span>
          <span className="text-[15px]">{SITE_NAME}</span>
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href} className={LINK}>{l.label}</a>
          ))}
          <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className={LINK}>
            Documentation<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </nav>

        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <AuthCta guestLabel="Get started" className={`${BTN_PRIMARY} !min-h-10 !px-4`} />
          <button
            ref={toggleRef}
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md text-ink hover:bg-subtle md:hidden"
          >
            {open ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
          </button>
        </div>
      </div>

      <nav id="mobile-menu" aria-label="Main (mobile)" hidden={!open} className="border-t border-line bg-canvas md:hidden">
        <ul className={`${CONTAINER} py-2`}>
          {NAV_LINKS.map((l) => (
            <li key={l.href}>
              <a href={l.href} onClick={() => setOpen(false)} className="block rounded-md px-1 py-3 text-base text-ink hover:bg-subtle">
                {l.label}
              </a>
            </li>
          ))}
          <li>
            <a
              href={DOCS_URL} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-md px-1 py-3 text-base text-ink hover:bg-subtle"
            >
              <BookOpen className="h-4 w-4" aria-hidden="true" /> Documentation
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </li>
          <li className="border-t border-line pt-2">
            <Link href="/login" onClick={() => setOpen(false)} className="block rounded-md px-1 py-3 text-base text-ink hover:bg-subtle">Log in</Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}
