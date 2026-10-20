import { ImageResponse } from "next/og";

export const dynamic = "force-static";

const SIZES: Record<string, { size: number; pad: number }> = {
  "192": { size: 192, pad: 0.2 },
  "512": { size: 512, pad: 0.2 },
  // Maskable icons keep the artwork inside the central 80% so OS masks never crop it.
  "maskable-512": { size: 512, pad: 0.3 },
  "apple-180": { size: 180, pad: 0.2 },
};

export function generateStaticParams() {
  return Object.keys(SIZES).map((name) => ({ name }));
}

/** App icons drawn at build time (solid colours, no image files to commit). */
export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const spec = SIZES[name];
  if (!spec) return new Response("Not found", { status: 404 });
  const inner = Math.round(spec.size * (1 - spec.pad * 2));
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "#4F46E5" }}>
        <svg width={inner} height={inner} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      </div>
    ),
    { width: spec.size, height: spec.size },
  );
}
