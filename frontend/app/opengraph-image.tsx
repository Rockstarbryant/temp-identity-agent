import { ImageResponse } from "next/og";

export const alt = "Temp Identity Agent: sign up for websites without exposing your primary inbox";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** Social preview drawn at build time with solid colours (no image file to maintain). */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#183C32", color: "#F8F8F5", padding: 72 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ width: 56, height: 56, borderRadius: 12, background: "#276749", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
          </div>
          <div style={{ fontSize: 34, fontWeight: 600 }}>Temp Identity Agent</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 76, lineHeight: 1.05, fontWeight: 700, maxWidth: 980 }}>Sign up for websites without using your primary mail.</div>
          <div style={{ fontSize: 30, color: "#D8A45B" }}>Paste a link. Get your login. Supported sites, with a manual fallback.</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
