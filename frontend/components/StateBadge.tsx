import { AlertTriangle, Ban, CheckCircle2, CircleHelp, Clock, Hourglass, Loader2, Mail, XCircle } from "lucide-react";
import Badge from "@/components/ui/Badge";
import { StatusGroup, statusMeta } from "@/lib/jobStatus";

const ICONS: Record<StatusGroup, React.ReactNode> = {
  running: <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />,
  waiting_user: <AlertTriangle className="h-3 w-3" aria-hidden="true" />,
  waiting_email: <Mail className="h-3 w-3" aria-hidden="true" />,
  completed: <CheckCircle2 className="h-3 w-3" aria-hidden="true" />,
  failed: <XCircle className="h-3 w-3" aria-hidden="true" />,
  cancelled: <Ban className="h-3 w-3" aria-hidden="true" />,
  expired: <Hourglass className="h-3 w-3" aria-hidden="true" />,
  unknown: <CircleHelp className="h-3 w-3" aria-hidden="true" />,
};

/** Job status as text + icon + colour. Accepts any string so an unknown backend state is shown honestly. */
export default function StateBadge({ state }: { state: string }) {
  const meta = statusMeta(state);
  return (
    <Badge tone={meta.tone} icon={ICONS[meta.group] ?? <Clock className="h-3 w-3" aria-hidden="true" />}>
      {meta.label}
    </Badge>
  );
}
