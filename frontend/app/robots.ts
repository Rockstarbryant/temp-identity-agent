import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/** The homepage and sign-in pages are public; everything behind login is kept out of search indexes. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/new", "/dashboard", "/jobs/", "/accounts", "/mailboxes", "/settings", "/notifications", "/oauth/", "/direct", "/@direct", "/icons/"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
