import type { Metadata } from "next";
import MarketingNav from "@/components/marketing/MarketingNav";
import {
  Fallback, FaqSection, FinalCta, Footer, Hero, InboxSection, Modes, Problem, Solution, Trust, VaultSection,
} from "@/components/marketing/Sections";
import { REPO_URL, SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

const TITLE = "Temp Identity Agent — Simplify Website Registration";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: SITE_DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: TITLE,
    description: SITE_DESCRIPTION,
  },
  twitter: { card: "summary_large_image", title: TITLE, description: SITE_DESCRIPTION },
};

// The copyright year in the footer is computed at build time; rebuild at least daily.
export const revalidate = 86400;

/**
 * Structured data describes only what is true and visible on the page. There is deliberately no
 * Organization, rating, review, price or contact data, because none has been established.
 */
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: SITE_NAME,
      description: SITE_DESCRIPTION,
      inLanguage: "en",
    },
    {
      "@type": "SoftwareApplication",
      "@id": `${SITE_URL}/#app`,
      name: SITE_NAME,
      url: SITE_URL,
      description: SITE_DESCRIPTION,
      applicationCategory: "UtilitiesApplication",
      operatingSystem: "Web",
      isPartOf: { "@id": `${SITE_URL}/#website` },
      sameAs: [REPO_URL],
    },
  ],
};

// "<" is escaped so the JSON can never close the script element.
const jsonLdString = JSON.stringify(jsonLd).replace(/</g, "\\u003c");

export default function MarketingHomePage() {
  return (
    <div className="marketing min-h-dvh bg-canvas text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:shadow-sm"
      >
        Skip to content
      </a>
      <MarketingNav />
      <main id="main">
        <Hero />
        <Problem />
        <Solution />
        <Modes />
        <div id="features" className="scroll-mt-16">
          <Fallback />
          <VaultSection />
          <InboxSection />
        </div>
        <Trust />
        <FaqSection />
        <FinalCta />
      </main>
      <Footer />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString }} />
    </div>
  );
}
