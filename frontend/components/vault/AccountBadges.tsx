import { CheckCircle2, Hourglass, Trash2, UserRound } from "lucide-react";
import { TemporaryAccountSummary } from "@/lib/api";
import Badge from "@/components/ui/Badge";

export function AccountStatusBadge({ status }: { status: TemporaryAccountSummary["status"] | string }) {
  if (status === "active") return <Badge tone="success" icon={<CheckCircle2 className="h-3 w-3" aria-hidden="true" />}>Active</Badge>;
  if (status === "expired") return <Badge tone="neutral" icon={<Hourglass className="h-3 w-3" aria-hidden="true" />}>Expired</Badge>;
  if (status === "deleted") return <Badge tone="neutral" icon={<Trash2 className="h-3 w-3" aria-hidden="true" />}>Removed</Badge>;
  return <Badge tone="neutral">Unknown status</Badge>;
}

export function AccountTypeBadges({ account }: { account: Pick<TemporaryAccountSummary, "permanent" | "manual"> }) {
  return (
    <>
      <Badge>{account.permanent ? "Permanent identity" : "Temporary identity"}</Badge>
      {account.manual && <Badge tone="accent" icon={<UserRound className="h-3 w-3" aria-hidden="true" />}>Signed up manually</Badge>}
    </>
  );
}
