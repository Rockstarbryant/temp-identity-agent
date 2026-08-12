"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, logout, isAuthenticated, User } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login?next=/settings");
      return;
    }
    getMe().then(setUser).catch(() => setUser(null));
  }, [router]);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  if (!user) {
    return <div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <h1 className="text-xl font-semibold">Settings</h1>
      <dl className="space-y-3 rounded-md border border-black/10 p-4 text-sm">
        <div className="flex justify-between"><dt className="text-black/50">Username</dt><dd>{user.username}</dd></div>
        {user.email && <div className="flex justify-between"><dt className="text-black/50">Email</dt><dd>{user.email}</dd></div>}
        <div className="flex justify-between">
          <dt className="text-black/50">Member since</dt>
          <dd>{new Date(user.date_joined).toLocaleDateString()}</dd>
        </div>
      </dl>
      <p className="text-xs text-black/40">
        Temporary accounts you create expire automatically based on your organization&apos;s
        retention policy. You can delete any account early from the vault.
      </p>
      <button onClick={handleLogout} className="text-sm text-red-600 hover:text-red-700">
        Log out
      </button>
    </div>
  );
}
