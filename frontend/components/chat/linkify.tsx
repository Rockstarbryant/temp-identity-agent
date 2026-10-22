import { ReactNode } from "react";
import { isSafeHttpUrl } from "@/lib/format";

const URL_RE = /(https?:\/\/[^\s<>"')]+[^\s<>"').,;:!?])/g;

/** Plain text with web addresses turned into links. Only http(s) links are made clickable. */
export function linkify(text: string): ReactNode[] {
  const parts = text.split(URL_RE);
  return parts.map((part, i) =>
    i % 2 === 1 && isSafeHttpUrl(part) ? (
      <a key={i} href={part} target="_blank" rel="noopener noreferrer nofollow" className="break-all underline underline-offset-2">
        {part}
      </a>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}
