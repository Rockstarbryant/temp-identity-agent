"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import {
  getMe, logout, isAuthenticated, getProfile, getEmailConnection, listApiKeys,
  AccountMode, ApiKeySummary, EmailConnection, ProfileData, ProfileEntry,
} from "@/lib/api";
import { useCachedData } from "@/lib/useCachedData";
import { Loader2 } from "lucide-react";
import AccountTypeCard from "@/components/settings/AccountTypeCard";
import DetailsCard from "@/components/settings/DetailsCard";
import EmailCard from "@/components/settings/EmailCard";
import McpCard from "@/components/settings/McpCard";
import Section from "@/components/settings/Section";

const GMAIL_NOTICES: Record<string, string> = {
  connected: "Gmail connected.",
  denied: "Google sign-in was cancelled, so nothing was connected.",
  error: "Could not connect Gmail. Try again, or use an app password.",
};

function SettingsInner() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    if (!isAuthenticated()) router.push("/login?next=/settings");
  }, [router]);

  const { data: user } = useCachedData("me", getMe);
  const { data: profile, mutate: mutateProfile, refresh: refreshProfile } = useCachedData<ProfileData>("profile", getProfile);
  const { data: email, mutate: mutateEmail, refresh: refreshEmail } = useCachedData<EmailConnection>("email-connection", getEmailConnection);
  const { data: keys, mutate: mutateKeys } = useCachedData<ApiKeySummary[]>("api-keys", listApiKeys);
  const [notice, setNotice] = useState<string | null>(null);

  // Coming back from Google's consent screen.
  useEffect(() => {
    const g = params.get("gmail");
    if (!g) return;
    setNotice(GMAIL_NOTICES[g] ?? null);
    refreshEmail();
    router.replace("/settings");
  }, [params, refreshEmail, router]);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  if (!user || !profile || !email) {
    return <div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="text-xl font-semibold">Settings</h1>

      <AccountTypeCard
        mode={profile.account_mode}
        emailConnected={email.connected}
        onChange={(m: AccountMode) => mutateProfile((p) => (p ? { ...p, account_mode: m } : p))}
      />

      <EmailCard connection={email} notice={notice} onChange={(c) => { mutateEmail(() => c); refreshProfile(); }} />

      <DetailsCard
        profile={profile}
        onChange={(entries: ProfileEntry[]) => mutateProfile((p) => (p ? { ...p, entries } : p))}
      />

      <McpCard keys={keys ?? []} onChange={(k) => mutateKeys(() => k)} />

      <Section title="Account">
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between"><dt className="text-black/50">Username</dt><dd>{user.username}</dd></div>
          {user.email && <div className="flex justify-between"><dt className="text-black/50">Email</dt><dd className="break-all pl-4 text-right">{user.email}</dd></div>}
          <div className="flex justify-between">
            <dt className="text-black/50">Member since</dt>
            <dd>{new Date(user.date_joined).toLocaleDateString()}</dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-black/40">
          Temporary accounts expire automatically based on your organization&apos;s retention policy. You can delete any
          account early from the vault.
        </p>
        <button onClick={handleLogout} className="mt-3 text-sm text-red-600 hover:text-red-700">
          Log out
        </button>
      </Section>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>}>
      <SettingsInner />
    </Suspense>
  );
}
