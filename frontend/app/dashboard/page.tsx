"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listRegistrationJobs, isAuthenticated, RegistrationJob } from "@/lib/api";
import StateBadge from "@/components/StateBadge";
import { Plus, Loader2 } from "lucide-react";

export default function DashboardPage() {
  const [jobs, setJobs] = useState<RegistrationJob[] | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login?next=/dashboard");
      return;
    }
    listRegistrationJobs()
      .then((data) => setJobs(data.results))
      .catch(() => setJobs([]));
  }, [router]);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Your jobs</h1>
        <Link href="/" className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent/90">
          <Plus className="h-4 w-4" /> New
        </Link>
      </div>

      {jobs === null ? (
        <div className="flex justify-center py-12 text-black/40"><Loader2 className="h-5 w-5 animate-spin" /></div>
      ) : jobs.length === 0 ? (
        <p className="py-12 text-center text-sm text-black/50">
          No jobs yet. <Link href="/" className="text-accent hover:underline">Create one</Link> to get started.
        </p>
      ) : (
        <ul className="divide-y divide-black/10 rounded-md border border-black/10">
          {jobs.map((job) => (
            <li key={job.id}>
              <Link href={`/jobs/${job.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-black/[0.02]">
                <div>
                  <p className="font-medium">{job.domain}</p>
                  <p className="text-xs text-black/40">{new Date(job.created_at).toLocaleString()}</p>
                </div>
                <StateBadge state={job.state} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
