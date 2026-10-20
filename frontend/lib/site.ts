/**
 * Public site facts used by metadata, the sitemap and the marketing homepage.
 *
 * SITE_URL: set NEXT_PUBLIC_SITE_URL in the frontend environment to change it. The fallback is the
 * frontend address already configured for this project (FRONTEND_URL in the project's .env).
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://logindirect.vercel.app").replace(/\/+$/, "");

export const SITE_NAME = "Temp Identity Agent";

export const REPO_URL = "https://github.com/Rockstarbryant/temp-identity-agent";

/** The project's documentation lives in the repository's docs/ folder. */
export const DOCS_URL = `${REPO_URL}/tree/HEAD/docs`;

/** Link to one file in docs/. Only pass files that exist in the repository. */
export const docUrl = (file: string) => `${REPO_URL}/blob/HEAD/docs/${file}`;

export const SITE_DESCRIPTION =
  "Temp Identity Agent helps you register for supported websites with a temporary or connected email, retrieves verification codes, generates a unique password for each site, and saves your login credentials in a vault.";
