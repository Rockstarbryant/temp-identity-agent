import Link from "next/link";
import {
  ArrowRight, ChevronDown, ExternalLink, FileText, Github, Inbox, KeyRound, ShieldCheck,
} from "lucide-react";
import { DOCS_URL, REPO_URL, SITE_NAME, docUrl } from "@/lib/site";
import AuthCta from "./AuthCta";
import {
  DEFINITION, FALLBACK_STEPS, FAQ, NAV_LINKS, PERMANENT_FEATURES, PROBLEMS, STEPS, TEMPORARY_FEATURES,
} from "./content";
import { InboxIllustration, ManualKitIllustration, VaultIllustration, WorkflowPreview } from "./Illustrations";
import { BTN_GHOST_ON_DEEP, BTN_ON_DEEP, BTN_PRIMARY, BTN_SECONDARY, CONTAINER, EYEBROW, H2, SECTION } from "./ui";

const PROBLEM_ICONS = {
  inbox: Inbox,
  form: FileText,
  key: KeyRound,
} as const;

function Check() {
  return (
    <svg viewBox="0 0 16 16" className="mt-1 h-4 w-4 shrink-0 text-accent-strong" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m3.5 8.5 3 3 6-7" />
    </svg>
  );
}

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="pb-10 pt-10 sm:pt-16 lg:pb-16 lg:pt-20">
      <div className={`${CONTAINER} grid items-center gap-12 lg:grid-cols-[1.08fr_0.92fr] lg:gap-16`}>
        <div>
          <p className={`${EYEBROW} rise`}>Personal account-registration assistant</p>
          <h1
            id="hero-title"
            className="rise rise-2 mt-4 font-display text-[clamp(2.5rem,5vw,4.5rem)] font-semibold leading-[1.05] tracking-tight"
          >
            Sign up for websites without exposing your primary inbox.
          </h1>
          <p className="rise rise-3 mt-5 max-w-xl text-lg leading-relaxed text-ink/90">
            Paste a website link. {SITE_NAME} handles supported registration forms, retrieves verification codes,
            generates unique passwords, and saves your login credentials in one place.
          </p>
          <p className="rise rise-3 mt-3 max-w-xl text-base leading-relaxed text-muted">
            Less time filling forms. Fewer reasons to hand out your main email address. No more reusing the same password everywhere.
          </p>
          <div className="rise rise-3 mt-8 flex flex-col gap-3 sm:flex-row">
            <AuthCta guestLabel="Try Temp Identity Agent" authedLabel="Open Temp Identity Agent" className={BTN_PRIMARY}>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </AuthCta>
            <a href="#how-it-works" className={BTN_SECONDARY}>See How It Works</a>
          </div>
          <p className="rise rise-3 mt-5 max-w-xl text-sm text-muted">
            Temporary and permanent account modes. Automated registration with a manual fallback when needed.
          </p>
        </div>
        <WorkflowPreview className="rise rise-2 mx-auto w-full max-w-md lg:max-w-none" />
      </div>

      <div className={`${CONTAINER} mt-12 lg:mt-16`}>
        <p className="max-w-3xl border-l-2 border-warm pl-4 text-base leading-relaxed text-ink/90">
          <strong className="font-semibold">In short: </strong>
          {DEFINITION}
        </p>
      </div>
    </section>
  );
}

export function Problem() {
  return (
    <section aria-labelledby="problem-title" className={`${SECTION} border-t border-line`}>
      <div className={CONTAINER}>
        <div className="reveal max-w-2xl">
          <p className={EYEBROW}>The problem</p>
          <h2 id="problem-title" className={`${H2} mt-3`}>Registration shouldn&apos;t be the hardest part of using a website.</h2>
          <p className="mt-5 text-lg leading-relaxed text-muted">
            You find something worth trying. Then comes the signup form, another email verification, and another password to
            remember. Before you reach what you came for, you&apos;ve already done too much work.
          </p>
        </div>
        <div className="reveal mt-12 grid gap-10 md:grid-cols-3 md:gap-0 md:divide-x md:divide-line">
          {PROBLEMS.map((p) => {
            const Icon = PROBLEM_ICONS[p.icon];
            return (
              <article key={p.title} className="md:px-8 md:first:pl-0 md:last:pr-0">
                <Icon className="h-6 w-6 text-accent-strong" aria-hidden="true" />
                <h3 className="mt-4 text-lg font-semibold">{p.title}</h3>
                <p className="mt-2 leading-relaxed text-muted">{p.text}</p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function Solution() {
  return (
    <section id="how-it-works" aria-labelledby="solution-title" className={`${SECTION} bg-subtle`}>
      <div className={CONTAINER}>
        <div className="reveal max-w-2xl">
          <p className={EYEBROW}>How it works</p>
          <h2 id="solution-title" className={`${H2} mt-3`}>One link. A simpler way to sign up.</h2>
          <p className="mt-5 text-lg leading-relaxed text-muted">
            {SITE_NAME} brings supported registration steps into one workflow, from preparing the form to retrieving
            verification messages and saving your credentials.
          </p>
        </div>

        <ol className="reveal mt-12 grid gap-8 md:grid-cols-4 md:gap-6">
          {STEPS.map((s, i) => (
            <li key={s.title} className="relative flex gap-4 md:block">
              {i < STEPS.length - 1 && (
                <span aria-hidden="true" className="absolute left-[19px] top-11 h-[calc(100%-1rem)] w-px bg-line-strong md:left-12 md:top-[19px] md:h-px md:w-[calc(100%-3rem)]" />
              )}
              <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface font-display text-lg font-semibold text-accent-strong">
                {i + 1}
              </span>
              <div className="md:mt-4">
                <h3 className="text-base font-semibold">{s.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="reveal mt-12 max-w-2xl rounded-lg border border-line bg-surface px-5 py-4 text-sm leading-relaxed text-muted">
          Some websites require manual completion. When supported, {SITE_NAME} prepares the registration details so you can continue yourself.
        </p>
      </div>
    </section>
  );
}

function ModePanel({
  badge, title, description, features, useCase, tone,
}: { badge: string; title: string; description: string; features: readonly string[]; useCase: string; tone: "default" | "keep" }) {
  return (
    <article className="flex flex-col rounded-2xl border border-line bg-surface p-6 sm:p-8">
      <span
        className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold ${
          tone === "default" ? "bg-accent-fill text-white" : "border border-warm bg-warm/15 text-ink"
        }`}
      >
        {badge}
      </span>
      <h3 className="mt-5 font-display text-2xl font-semibold leading-tight">{title}</h3>
      <p className="mt-3 leading-relaxed text-muted">{description}</p>
      <ul className="mt-6 flex-1 space-y-3 text-[15px]">
        {features.map((f) => (
          <li key={f} className="flex gap-3"><Check /><span>{f}</span></li>
        ))}
      </ul>
      <p className="mt-6 border-t border-line pt-5 text-sm italic text-muted">{useCase}</p>
    </article>
  );
}

export function Modes() {
  return (
    <section id="modes" aria-labelledby="modes-title" className={SECTION}>
      <div className={CONTAINER}>
        <div className="reveal max-w-2xl">
          <p className={EYEBROW}>Account modes</p>
          <h2 id="modes-title" className={`${H2} mt-3`}>Choose the right email for the account.</h2>
          <p className="mt-5 text-lg leading-relaxed text-muted">
            Not every website deserves a permanent place in your inbox. And some accounts are worth keeping. {SITE_NAME} supports both situations.
          </p>
        </div>
        <div className="reveal mt-12 grid gap-6 lg:grid-cols-2">
          <ModePanel
            tone="default"
            badge="Default mode"
            title="For websites you're just trying out."
            description="Register using a temporary email address instead of unnecessarily exposing your primary inbox."
            features={TEMPORARY_FEATURES}
            useCase="Useful for exploring prototypes, unfamiliar tools, and websites you may not revisit."
          />
          <ModePanel
            tone="keep"
            badge="For accounts you intend to keep"
            title="Keep the accounts that matter."
            description="Use your connected Gmail account for supported registration workflows when you want to maintain access to a website."
            features={PERMANENT_FEATURES}
            useCase="Useful for frequently used websites, services, and portals."
          />
        </div>
        <p className="reveal mt-6 max-w-3xl text-sm leading-relaxed text-muted">
          Permanent mode removes the temporary-account expiry rule; it does not guarantee that an external website or connected email account will remain available forever.
        </p>
      </div>
    </section>
  );
}

export function Fallback() {
  return (
    <section aria-labelledby="fallback-title" className={`${SECTION} bg-subtle`}>
      <div className={`${CONTAINER} grid items-center gap-12 lg:grid-cols-2 lg:gap-16`}>
        <div className="reveal">
          <p className={EYEBROW}>Manual fallback</p>
          <h2 id="fallback-title" className={`${H2} mt-3`}>When automation hits a wall, you still have a way forward.</h2>
          <p className="mt-5 text-lg leading-relaxed text-muted">
            Some websites restrict automated browsers or require CAPTCHA challenges. Instead of leaving you with nothing,
            {" "}{SITE_NAME} can prepare the registration details for you to enter manually when supported.
          </p>
          <ol className="mt-8 space-y-4">
            {FALLBACK_STEPS.map((s, i) => (
              <li key={s} className="flex gap-4">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-fill text-xs font-semibold text-white">{i + 1}</span>
                <span className="leading-relaxed">{s}</span>
              </li>
            ))}
          </ol>
          <p className="mt-6 text-sm text-muted">
            It never bypasses CAPTCHAs or other security checks, and it cannot promise every registration will succeed.{" "}
            <a href="#faq" className="font-medium text-accent-strong underline underline-offset-2">Read the limitations</a>.
          </p>
        </div>
        <ManualKitIllustration className="reveal mx-auto w-full max-w-md" />
      </div>
    </section>
  );
}

export function VaultSection() {
  return (
    <section aria-labelledby="vault-title" className={SECTION}>
      <div className={`${CONTAINER} grid items-center gap-12 lg:grid-cols-2 lg:gap-16`}>
        <VaultIllustration className="reveal order-2 mx-auto w-full max-w-md lg:order-1" />
        <div className="reveal order-1 lg:order-2">
          <p className={EYEBROW}>Credentials vault</p>
          <h2 id="vault-title" className={`${H2} mt-3`}>Every account gets its own password.</h2>
          <p className="mt-5 text-lg leading-relaxed text-muted">
            {SITE_NAME} generates a unique password for each supported registration and saves the resulting credentials in
            your vault, so you don&apos;t have to remember every password yourself.
          </p>
          <p className="mt-4 leading-relaxed text-muted">
            Retrieve your saved login details when you need them, subject to the account&apos;s retention rules. Passwords stay hidden
            until you choose to reveal them, and you can delete a saved account from the vault at any time.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            A vault entry is not a shield: a website can still be breached, and deleting a vault entry does not delete your account on that website.
          </p>
        </div>
      </div>
    </section>
  );
}

export function InboxSection() {
  return (
    <section aria-labelledby="inbox-title" className={`${SECTION} bg-subtle`}>
      <div className={`${CONTAINER} grid items-center gap-12 lg:grid-cols-2 lg:gap-16`}>
        <div className="reveal">
          <p className={EYEBROW}>Built-in inbox</p>
          <h2 id="inbox-title" className={`${H2} mt-3`}>The verification inbox is already part of the workflow.</h2>
          <p className="mt-5 text-lg leading-relaxed text-muted">
            When a website sends a verification code, link, or additional instructions to the email address used for registration,
            {" "}{SITE_NAME} lets you access the associated inbox through the platform when the provider supports it.
          </p>
          <p className="mt-4 leading-relaxed text-muted">
            Verification codes and links are pulled out for you. Everything else sent to that address stays readable in the same place.
            Message availability depends on the email provider and its retention rules.
          </p>
        </div>
        <InboxIllustration className="reveal mx-auto w-full max-w-md" />
      </div>
    </section>
  );
}

const TRUST_ITEMS: { title: string; text: string; href?: string; link?: string }[] = [
  {
    title: "Credential security",
    text: "Saved passwords and mailbox credentials are stored with authenticated encryption (Fernet). The key lives in server configuration, not in the code.",
    href: docUrl("security.md"),
    link: "Security documentation",
  },
  {
    title: "Email account connections",
    text: "Permanent mode reads verification mail from the Gmail account you connect, opened read-only, and only messages that arrive after a task starts. You can disconnect it in Settings.",
    href: docUrl("settings-and-mcp.md"),
    link: "Settings documentation",
  },
  {
    title: "Temporary data retention",
    text: "Temporary credentials are kept for a configured period (7 days by default). After that the stored password and mailbox credentials are scrubbed, not just hidden.",
    href: docUrl("security.md"),
    link: "How retention works",
  },
  {
    title: "Permanent account storage",
    text: "Permanent-mode credentials stay in your vault until you delete them. That does not guarantee a website or your email account will stay available.",
  },
  {
    title: "AI and MCP access",
    text: "The agent can only use a fixed set of allowed actions and inspects pages as structured data, not raw HTML. Page content is processed by a third-party AI model provider. AI clients you authorize through MCP can start and track registrations, and you can revoke them at any time.",
    href: docUrl("settings-and-mcp.md"),
    link: "MCP documentation",
  },
  {
    title: "Deletion and disconnection",
    text: "Delete any saved account from the vault, disconnect your email and sign-in accounts, and revoke API keys, all from Settings. Deleting a vault entry does not delete your account on the website.",
  },
];

export function Trust() {
  return (
    <section id="trust" aria-labelledby="trust-title" className={`${SECTION} bg-deep text-white`}>
      <div className={CONTAINER}>
        <div className="reveal max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-warm">Trust and responsible use</p>
          <h2 id="trust-title" className={`${H2} mt-3`}>Convenience should come with clarity.</h2>
          <p className="mt-5 text-lg leading-relaxed text-white/75">
            {SITE_NAME} helps simplify registration and reduce unnecessary exposure of your primary email address. It also handles
            sensitive information, so understanding how your data and credentials are managed matters.
          </p>
        </div>
        <dl className="reveal mt-12 grid gap-x-12 gap-y-9 md:grid-cols-2">
          {TRUST_ITEMS.map((t) => (
            <div key={t.title} className="border-t border-white/20 pt-5">
              <dt className="flex items-center gap-2 text-base font-semibold">
                <ShieldCheck className="h-4 w-4 shrink-0 text-warm" aria-hidden="true" /> {t.title}
              </dt>
              <dd className="mt-2 text-[15px] leading-relaxed text-white/75">
                {t.text}
                {t.href && (
                  <>
                    {" "}
                    <a href={t.href} target="_blank" rel="noopener noreferrer" className="whitespace-nowrap font-medium text-white underline underline-offset-2">
                      {t.link}<span className="sr-only"> (opens in a new tab)</span>
                    </a>
                  </>
                )}
              </dd>
            </div>
          ))}
        </dl>
        <p className="reveal mt-12 max-w-2xl text-sm leading-relaxed text-white/70">
          Use truthful information where it is required, particularly for official, financial, identity-verification, and other sensitive
          services. Temporary email does not make you anonymous, and {SITE_NAME} does not remove every privacy or account-security risk.
        </p>
      </div>
    </section>
  );
}

export function FaqSection() {
  return (
    <section id="faq" aria-labelledby="faq-title" className={SECTION}>
      <div className={`${CONTAINER} grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16`}>
        <div className="reveal">
          <p className={EYEBROW}>FAQ</p>
          <h2 id="faq-title" className={`${H2} mt-3`}>Good questions. Straight answers.</h2>
          <p className="mt-4 text-muted">
            More detail lives in the{" "}
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="font-medium text-accent-strong underline underline-offset-2">
              project documentation<span className="sr-only"> (opens in a new tab)</span>
            </a>.
          </p>
        </div>
        {/* Native <details>: keyboard accessible, state exposed to assistive tech, and the answers are in the HTML. */}
        <div className="reveal divide-y divide-line border-y border-line">
          {FAQ.map((item) => (
            <details key={item.q} className="group">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-4 rounded-md py-5 text-left font-semibold marker:hidden [&::-webkit-details-marker]:hidden">
                <span>{item.q}</span>
                <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <p className="pb-5 pr-8 leading-relaxed text-muted">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="pb-16 sm:pb-20 lg:pb-28">
      <div className={CONTAINER}>
        <div className="reveal rounded-3xl bg-deep px-6 py-14 text-center text-white sm:px-12 sm:py-20">
          <h2 id="cta-title" className="mx-auto max-w-2xl font-display text-[clamp(1.8rem,3.4vw,3rem)] font-semibold leading-[1.15] tracking-tight">
            Spend less time signing up. More time using what you came for.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg text-white/75">
            Paste a website link and let {SITE_NAME} handle the supported registration steps.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <AuthCta guestLabel="Try Temp Identity Agent" authedLabel="Open Temp Identity Agent" className={BTN_ON_DEEP}>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </AuthCta>
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className={BTN_GHOST_ON_DEEP}>
              <Github className="h-4 w-4" aria-hidden="true" /> Explore the Project on GitHub
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

export function Footer() {
  const year = new Date().getFullYear();
  const link = "text-sm text-muted hover:text-ink";
  return (
    <footer className="border-t border-line">
      <div className={`${CONTAINER} grid gap-10 py-12 md:grid-cols-[1.4fr_1fr_1fr]`}>
        <div>
          <p className="flex items-center gap-2 font-semibold">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent-fill text-white">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </span>
            {SITE_NAME}
          </p>
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted">
            A personal account-registration assistant: supported registrations, verification messages, unique passwords, and a credential vault.
          </p>
        </div>
        <nav aria-label="Footer">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Explore</h2>
          <ul className="mt-3 space-y-2">
            {NAV_LINKS.map((l) => (
              <li key={l.href}><a href={l.href} className={link}>{l.label}</a></li>
            ))}
          </ul>
        </nav>
        <nav aria-label="Project">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Project</h2>
          <ul className="mt-3 space-y-2">
            <li>
              <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className={`${link} inline-flex items-center gap-1`}>
                GitHub <ExternalLink className="h-3 w-3" aria-hidden="true" /><span className="sr-only">(opens in a new tab)</span>
              </a>
            </li>
            <li>
              <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className={`${link} inline-flex items-center gap-1`}>
                Documentation <ExternalLink className="h-3 w-3" aria-hidden="true" /><span className="sr-only">(opens in a new tab)</span>
              </a>
            </li>
            <li><Link href="/login" className={link}>Log in</Link></li>
            <li><Link href="/register" className={link}>Sign up</Link></li>
          </ul>
        </nav>
      </div>
      <div className="border-t border-line">
        <p className={`${CONTAINER} py-5 text-xs text-muted`}>&copy; {year} {SITE_NAME}.</p>
      </div>
    </footer>
  );
}
