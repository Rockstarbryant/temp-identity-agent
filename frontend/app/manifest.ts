import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  const manifest = {
    id: "/",
    name: "Temp Identity Agent",
    short_name: "Temp Identity",
    description: "Create a temporary account without using your personal email.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#FAFAFA",
    theme_color: "#FFFFFF",
    categories: ["productivity", "utilities", "security"],
    icons: [
      { src: "/icons/192", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/512", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "New task", url: "/", description: "Start a registration or form task" },
      { name: "Activity", url: "/dashboard" },
      { name: "Mailboxes", url: "/mailboxes" },
      { name: "Identity Vault", url: "/accounts" },
    ],
    // Lets Android share a page from the browser straight to the app. It lands on a
    // confirmation screen (/direct), so sharing never starts a task by itself.
    share_target: {
      action: "/direct",
      method: "GET",
      params: { title: "title", text: "text", url: "url" },
    },
  };
  // share_target is part of the web app manifest spec but not of Next's TypeScript type.
  return manifest as MetadataRoute.Manifest;
}
