"use client";

import { KeyboardEvent, Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AccountMode, ApiKeySummary, ConnectedAccount, EmailConnection, ProfileData, ProfileEntry,
  getEmailConnection, getMe, getProfile, listApiKeys, listConnectedAccounts, logout,
} from "@/lib/api";
import { stopNotifications } from "@/lib/notifications";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { formatDate } from "@/lib/format";
import AccountTypeCard from "@/components/settings/AccountTypeCard";
import DetailsCard from "@/components/settings/DetailsCard";
import EmailCard from "@/components/settings/EmailCard";
import ConnectedAccountsCard from "@/components/settings/ConnectedAccountsCard";
import McpCard from "@/components/settings/McpCard";
import Section from "@/components/settings/Section";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
import { ErrorState, PageSpinner } from "@/components/ui/States";
import { cn } from "@/components/ui/cn";

const GMAIL_NOTICES: Record<string, string> = {
  connected: "Gmail connected.",
  denied: "Google sign-in was cancelled, so nothing was connected.",
  error: "Could not connect Gmail. Try again, or use an app password.",
};

const TABS = [
  { id: "preferences", label: "Account and identity" },
  { id: "details", label: "Saved details" },
  { id: "email", label: "Email" },
  { id: "accounts", label: "Sign-in accounts" },
  { id: "developer", label: "Developer and MCP" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function SettingsInner() {
  const ready = useRequireAuth();
  const router = useRouter();
  const params = useSearchParams();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const requested = params.get("tab");
  const tab: TabId = TABS.some((t) => t.id === requested) ? (requested as TabId) : "preferences";

  const { data: user, error: userError, refresh: refreshUser } = useCachedData(ready ? "me" : null, getMe);
  const { data: profile, mutate: mutateProfile, refresh: refreshProfile, error: profileError } =
    useCachedData<ProfileData>(ready ? "profile" : null, getProfile);
  const { data: email, mutate: mutateEmail, refresh: refreshEmail, error: emailError } =
    useCachedData<EmailConnection>(ready ? "email-connection" : null, getEmailConnection);
  const { data: accounts, mutate: mutateAccounts, error: accountsError } =
    useCachedData<ConnectedAccount[]>(ready ? "connected-accounts" : null, listConnectedAccounts);
  const { data: keys, mutate: mutateKeys, error: keysError } =
    useCachedData<ApiKeySummary[]>(ready ? "api-keys" : null, listApiKeys);
  const [notice, setNotice] = useState<string | null>(null);

  // Coming back from Google's consent screen: show the result on the Email tab.
  useEffect(() => {
    const g = params.get("gmail");
    if (!g) return;
    setNotice(GMAIL_NOTICES[g] ?? null);
    void refreshEmail();
    router.replace("/settings?tab=email", { scroll: false });
  }, [params, refreshEmail, router]);

  function select(id: TabId) {
    router.replace(`/settings?tab=${id}`, { scroll: false });
  }

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = -1;
    if (e.key === "ArrowRight") next = (index + 1) % TABS.length;
    if (e.key === "ArrowLeft") next = (index - 1 + TABS.length) % TABS.length;
    if (e.key === "Home") next = 0;
    if (e.key === "End") next = TABS.length - 1;
    if (next < 0) return;
    e.preventDefault();
    select(TABS[next].id);
    tabRefs.current[TABS[next].id]?.focus();
  }

  async function handleLogout() {
    try {
      await logout();
    } finally {
      stopNotifications();
      router.push("/login");
    }
  }

  if (!ready) return <PageSpinner />;

  const loadFail = (err: unknown, retry?: () => void) =>
    err ? <ErrorState title="Could not load this section" message="Check your connection and try again." onRetry={retry} /> : <PageSpinner />;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Settings" description="Your identity preferences, saved details, email and integrations." />

      <div role="tablist" aria-label="Settings sections" className="-mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-line px-4 md:mx-0 md:px-0">
        {TABS.map((t, i) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              ref={(el) => { tabRefs.current[t.id] = el; }}
              type="button"
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={active}
              aria-controls={`panel-${t.id}`}
              tabIndex={active ? 0 : -1}
              onClick={() => select(t.id)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={cn(
                "-mb-px shrink-0 border-b-2 px-3 py-2.5 text-sm transition-colors",
                active ? "border-accent-strong font-medium text-accent-strong" : "border-transparent text-muted hover:text-ink",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="space-y-6">
        {tab === "preferences" && (
          <>
            {profile ? (
              <AccountTypeCard
                mode={profile.account_mode}
                emailConnected={!!email?.connected}
                onChange={(m: AccountMode) => mutateProfile((p) => (p ? { ...p, account_mode: m } : p))}
              />
            ) : loadFail(profileError, () => void refreshProfile())}

            {user ? (
              <Section title="Account" hint="Temporary identities expire automatically. You can delete any account early from the Identity Vault.">
                <dl className="space-y-3 text-sm">
                  <div className="flex justify-between gap-4"><dt className="text-muted">Username</dt><dd className="font-mono">{user.username}</dd></div>
                  {user.email && <div className="flex justify-between gap-4"><dt className="text-muted">Email</dt><dd className="break-all text-right font-mono">{user.email}</dd></div>}
                  <div className="flex justify-between gap-4"><dt className="text-muted">Member since</dt><dd>{formatDate(user.date_joined)}</dd></div>
                </dl>
                <div className="mt-4 border-t border-line pt-4">
                  <Button variant="danger-ghost" onClick={handleLogout}>Log out</Button>
                </div>
              </Section>
            ) : loadFail(userError, () => void refreshUser())}
          </>
        )}

        {tab === "details" &&
          (profile ? (
            <DetailsCard profile={profile} onChange={(entries: ProfileEntry[]) => mutateProfile((p) => (p ? { ...p, entries } : p))} />
          ) : loadFail(profileError, () => void refreshProfile()))}

        {tab === "email" &&
          (email ? (
            <EmailCard connection={email} notice={notice} onChange={(c) => { mutateEmail(() => c); void refreshProfile(); }} />
          ) : loadFail(emailError, () => void refreshEmail()))}

        {tab === "accounts" &&
          (accounts ? <ConnectedAccountsCard accounts={accounts} onChange={(a) => mutateAccounts(() => a)} /> : loadFail(accountsError))}

        {tab === "developer" &&
          (keys ? <McpCard keys={keys} onChange={(k) => mutateKeys(() => k)} /> : loadFail(keysError))}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <SettingsInner />
    </Suspense>
  );
}
