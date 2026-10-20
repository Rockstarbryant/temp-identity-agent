import { CheckCircle2, Clock, Copy, Globe, Inbox, KeyRound, Loader2, Mail, MailOpen } from "lucide-react";

/*
 * Lightweight, static illustrations built from the same components and tokens as the app.
 * All names, addresses, codes and dates are sample data and each figure is captioned as such.
 * They are exposed to assistive technology as a single described image, not as controls.
 */

function Frame({ label, caption, className = "", children }: { label: string; caption: string; className?: string; children: React.ReactNode }) {
  return (
    <figure role="img" aria-label={label} className={className}>
      <div aria-hidden="true" className="overflow-hidden rounded-xl border border-line bg-surface shadow-sm">{children}</div>
      <figcaption aria-hidden="true" className="mt-2 text-center text-xs text-muted">{caption}</figcaption>
    </figure>
  );
}

function TitleBar({ children, tag }: { children: React.ReactNode; tag: string }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-line bg-subtle px-4 py-2.5">
      <span className="truncate text-xs font-medium">{children}</span>
      <span className="shrink-0 rounded-full border border-line-strong bg-surface px-2 py-0.5 text-[10px] font-medium text-muted">{tag}</span>
    </div>
  );
}

export function WorkflowPreview({ className = "" }: { className?: string }) {
  const steps: { text: string; state: "done" | "active" }[] = [
    { text: "Opened the registration page", state: "done" },
    { text: "Filled in the form", state: "done" },
    { text: "Entered the verification code from the inbox", state: "done" },
  ];
  return (
    <Frame
      className={className}
      label="Illustrative example: a sample website address is submitted, the registration form is filled in, the email is verified, and the login is saved in the vault."
      caption="Illustrative example with sample data"
    >
      <TitleBar tag="Sample">Registration task</TitleBar>
      <div className="space-y-4 p-4">
        <div className="flex items-center gap-2 rounded-md border border-line-strong bg-canvas px-3 py-2.5">
          <Globe className="h-4 w-4 shrink-0 text-muted" />
          <span className="truncate font-mono text-xs">https://example.com/signup</span>
        </div>
        <ol className="space-y-2.5">
          {steps.map((s) => (
            <li key={s.text} className="flex items-start gap-2.5 text-sm">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong" />
              <span>{s.text}</span>
            </li>
          ))}
          <li className="flex items-start gap-2.5 text-sm text-muted">
            <Loader2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>Saving your login</span>
          </li>
        </ol>
        <div className="rounded-lg border border-accent/30 bg-accent-soft p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-accent-strong">
            <KeyRound className="h-3.5 w-3.5" /> Saved to your vault
          </p>
          <dl className="mt-2 space-y-1 text-xs">
            <div className="flex justify-between gap-3"><dt className="text-muted">Website</dt><dd className="font-mono">example.com</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-muted">Password</dt><dd className="font-mono tracking-widest">••••••••••••••••</dd></div>
          </dl>
        </div>
      </div>
    </Frame>
  );
}

export function ManualKitIllustration({ className = "" }: { className?: string }) {
  const rows = [
    ["Username", "quiet-otter-482"],
    ["Email", "quiet.otter@mail.example"],
    ["Password", "••••••••••••••••••••"],
  ];
  return (
    <Frame
      className={className}
      label="Illustrative example: a registration kit listing a sample username, email address and masked password, ready to copy into a website's own form."
      caption="Illustrative example with sample data"
    >
      <TitleBar tag="Sample">Sign up yourself · example.com</TitleBar>
      <dl className="divide-y divide-line">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between gap-3 px-4 py-3">
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="flex min-w-0 items-center gap-2 font-mono text-xs">
              <span className="truncate">{v}</span>
              <Copy className="h-3.5 w-3.5 shrink-0 text-muted" />
            </dd>
          </div>
        ))}
      </dl>
      <p className="border-t border-line bg-subtle px-4 py-3 text-xs text-muted">
        Paste these into the site&apos;s own form, then save the result to your vault.
      </p>
    </Frame>
  );
}

export function VaultIllustration({ className = "" }: { className?: string }) {
  const rows = [
    { site: "example.com", who: "sample@mail.example", kind: "Temporary", note: "Expires in 6 days", icon: Clock },
    { site: "docs.example.org", who: "sample@mail.example", kind: "Temporary", note: "Expires in 2 days", icon: Clock },
    { site: "portal.example.net", who: "you@your-gmail.example", kind: "Permanent", note: "No expiry rule", icon: KeyRound },
  ];
  return (
    <Frame
      className={className}
      label="Illustrative example: a vault listing three sample accounts, each with a website, an email address, a masked password, and a temporary or permanent label with expiry information."
      caption="Illustrative example with sample data"
    >
      <TitleBar tag="Sample">Identity Vault</TitleBar>
      <ul className="divide-y divide-line">
        {rows.map((r) => (
          <li key={r.site} className="px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <span className="truncate font-mono text-sm font-medium">{r.site}</span>
              <span className="flex shrink-0 items-center gap-1 rounded-md border border-line bg-subtle px-2 py-0.5 text-[11px] font-medium text-muted">
                <r.icon className="h-3 w-3" /> {r.kind}
              </span>
            </div>
            <p className="mt-0.5 truncate font-mono text-xs text-muted">{r.who}</p>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs">
              <span className="font-mono tracking-widest text-muted">••••••••••••</span>
              <span className="text-muted">{r.note}</span>
            </div>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

export function InboxIllustration({ className = "" }: { className?: string }) {
  return (
    <Frame
      className={className}
      label="Illustrative example: an inbox with a sample verification email showing a six-digit code and a second, unrelated newsletter message."
      caption="Illustrative example with sample data"
    >
      <TitleBar tag="Sample">Mailbox · sample@mail.example</TitleBar>
      <ul className="divide-y divide-line">
        <li className="flex items-start gap-2.5 bg-accent-soft px-4 py-3">
          <Mail className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">Confirm your email</p>
            <p className="truncate font-mono text-xs text-muted">no-reply@example.com</p>
            <p className="mt-2 inline-flex items-center gap-2 rounded-md border border-line bg-surface px-2.5 py-1 text-xs">
              <span className="text-muted">Verification code</span>
              <span className="font-mono text-sm font-semibold tracking-wider">482913</span>
            </p>
          </div>
        </li>
        <li className="flex items-start gap-2.5 px-4 py-3">
          <MailOpen className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <div className="min-w-0">
            <p className="truncate text-sm text-ink/80">This week at Example</p>
            <p className="truncate font-mono text-xs text-muted">news@example.com</p>
          </div>
        </li>
        <li className="flex items-center gap-2 px-4 py-2.5 text-xs text-muted">
          <Inbox className="h-3.5 w-3.5" /> Other messages sent to the address appear here too
        </li>
      </ul>
    </Frame>
  );
}
