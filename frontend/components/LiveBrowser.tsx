"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Globe, Keyboard, Loader2, MousePointerClick } from "lucide-react";
import { ApiError, getLiveView, sendLiveInput, type LiveFrame, type LiveInput } from "@/lib/api";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";

interface Props {
  jobId: string;
  /** The job is paused and needs the user: open automatically. */
  needsHuman: boolean;
  /** The job has finished: stop polling. */
  finished: boolean;
  /** Reports whether the server says the browser is currently waiting for the user's input. */
  onInteractiveChange?: (interactive: boolean) => void;
}

const POLL_MS = 1000;

/**
 * Preview of the agent's browser. The browser runs on the server, so this is a series of
 * screenshots fetched about once a second from the live endpoint, not a real remote browser.
 * Input (click, type, key, scroll) is only accepted while the server reports `interactive`,
 * which is when the job is paused and its browser is being held open for the user.
 */
export default function LiveBrowser({ jobId, needsHuman, finished, onInteractiveChange }: Props) {
  const [open, setOpen] = useState(false);
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [interactive, setInteractive] = useState(false);
  const [text, setText] = useState("");
  const [marker, setMarker] = useState<{ x: number; y: number; k: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  const notify = useRef(onInteractiveChange);
  notify.current = onInteractiveChange;

  useEffect(() => {
    if (needsHuman) setOpen(true);
  }, [needsHuman]);

  useEffect(() => {
    if (!open || finished) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      if (stopped) return;
      if (!document.hidden) {
        try {
          const res = await getLiveView(jobId, seq.current);
          if (stopped) return;
          if (res.seq !== undefined) seq.current = res.seq;
          if (res.frame) setFrame(res.frame);
          setInteractive(res.interactive);
          notify.current?.(res.interactive);
          setError(null);
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 429)) setError("Lost connection to the browser preview. Retrying.");
        }
      }
      timer = setTimeout(tick, POLL_MS);
    };
    void tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [open, finished, jobId]);

  // The click marker is a brief confirmation, not decoration: it disappears on its own.
  useEffect(() => {
    if (!marker) return;
    const t = setTimeout(() => setMarker(null), 700);
    return () => clearTimeout(t);
  }, [marker]);

  const send = useCallback(
    async (event: LiveInput) => {
      try {
        await sendLiveInput(jobId, event);
        setError(null);
      } catch (err) {
        setError(
          err instanceof ApiError && err.status === 409
            ? "The browser is not waiting for input right now."
            : "Could not send that. Try again.",
        );
      }
    },
    [jobId],
  );

  function onTap(e: React.MouseEvent<HTMLImageElement>) {
    if (!interactive || !frame) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    setMarker({ x: px, y: py, k: Date.now() });
    void send({
      type: "click",
      x: Math.round((px / rect.width) * frame.width),
      y: Math.round((py / rect.height) * frame.height),
    });
  }

  function submitText(submit: boolean) {
    if (!text) return;
    void send({ type: "type", text, submit });
    setText("");
  }

  const panelId = `browser-${jobId}`;

  return (
    <section className="overflow-hidden rounded-lg border border-line bg-surface" aria-label="Browser preview">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium hover:bg-subtle"
      >
        <span className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-muted" aria-hidden="true" />
          {needsHuman ? "Browser preview: your turn" : "Browser preview"}
        </span>
        {open ? <ChevronUp className="h-4 w-4 text-muted" aria-hidden="true" /> : <ChevronDown className="h-4 w-4 text-muted" aria-hidden="true" />}
      </button>

      {open && (
        <div id={panelId} className="space-y-3 border-t border-line p-3">
          {!frame ? (
            <div role="status" className="flex h-40 items-center justify-center gap-2 text-sm text-muted">
              {finished ? (
                "No browser session is active for this task."
              ) : (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Waiting for the browser to produce a screenshot
                </>
              )}
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 flex-1 truncate font-mono text-xs text-muted" title={frame.url}>{frame.url}</p>
                <Badge tone={interactive ? "warning" : "neutral"}>{interactive ? "Waiting for you" : "View only"}</Badge>
              </div>
              <div className="relative">
                {/* A data: URL of the screenshot returned by the API. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/jpeg;base64,${frame.image}`}
                  alt="Screenshot of the browser the agent is using"
                  onClick={onTap}
                  draggable={false}
                  className={`block w-full select-none rounded-md border border-line ${interactive ? "cursor-pointer" : ""}`}
                />
                {marker && (
                  <span
                    key={marker.k}
                    aria-hidden="true"
                    className="pointer-events-none absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent"
                    style={{ left: marker.x, top: marker.y }}
                  />
                )}
              </div>
              {!interactive && !finished && (
                <p className="text-xs text-muted">
                  This is a screenshot from a browser running on the server, refreshed about once a second. You can watch it but not click in it right now.
                </p>
              )}
            </>
          )}

          {interactive && frame && (
            <div className="space-y-2.5 rounded-md border border-line bg-subtle p-3">
              <p className="flex items-start gap-1.5 text-xs text-ink">
                <MousePointerClick className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Tap or click the screenshot to click in the page, for example the CAPTCHA checkbox. To type into a field, click it first, then use the box below.
              </p>
              <div className="flex gap-2">
                <div className="relative min-w-0 flex-1">
                  <Keyboard className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
                  <label htmlFor={`${panelId}-type`} className="sr-only">Text to type into the page</label>
                  <input
                    id={`${panelId}-type`}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitText(true);
                    }}
                    placeholder="Type text, then press Enter"
                    maxLength={300}
                    autoComplete="off"
                    className="min-h-9 w-full rounded-md border border-line-strong bg-surface py-1.5 pl-8 pr-2 text-sm"
                  />
                </div>
                <Button size="md" onClick={() => submitText(false)} disabled={!text}>Type</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {(["Enter", "Tab", "Backspace"] as const).map((k) => (
                  <Button key={k} size="sm" onClick={() => void send({ type: "key", key: k })}>{k}</Button>
                ))}
                <Button size="sm" onClick={() => void send({ type: "scroll", dy: -400 })}>Scroll up</Button>
                <Button size="sm" onClick={() => void send({ type: "scroll", dy: 400 })}>Scroll down</Button>
              </div>
            </div>
          )}

          {needsHuman && !interactive && frame && (
            <p className="text-xs text-muted">
              The browser is no longer waiting for you, so it has stopped accepting input. Use Continue to try again in a new browser session.
            </p>
          )}
          {error && <p role="alert" className="text-xs text-danger">{error}</p>}
        </div>
      )}
    </section>
  );
}
