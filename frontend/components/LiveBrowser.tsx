"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Eye, Keyboard, Loader2, MousePointerClick } from "lucide-react";
import { ApiError, getLiveView, sendLiveInput, type LiveFrame, type LiveInput } from "@/lib/api";

interface Props {
  jobId: string;
  /** The job is paused and needs the user: open automatically and allow input. */
  needsHuman: boolean;
  /** The job has finished; stop polling. */
  finished: boolean;
}

const POLL_MS = 1000;

/**
 * Live view of the agent's browser. The browser runs on our server, so this is
 * a stream of screenshots; while the job is paused, taps / typing / scrolling
 * are sent back and replayed there so a CAPTCHA can be solved by hand.
 */
export default function LiveBrowser({ jobId, needsHuman, finished }: Props) {
  const [open, setOpen] = useState(false);
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [interactive, setInteractive] = useState(false);
  const [text, setText] = useState("");
  const [ripple, setRipple] = useState<{ x: number; y: number; k: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  const imgRef = useRef<HTMLImageElement>(null);

  // Open automatically the moment a human is needed.
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
          setError(null);
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 429)) setError("Lost connection to the live view. Retrying…");
        }
      }
      timer = setTimeout(tick, POLL_MS);
    };
    tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [open, finished, jobId]);

  const send = useCallback(
    async (event: LiveInput) => {
      try {
        await sendLiveInput(jobId, event);
        setError(null);
      } catch (err) {
        setError(
          err instanceof ApiError && err.status === 409
            ? "The browser isn't waiting for input right now."
            : "Couldn't send that. Try again.",
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
    setRipple({ x: px, y: py, k: Date.now() });
    send({
      type: "click",
      x: Math.round((px / rect.width) * frame.width),
      y: Math.round((py / rect.height) * frame.height),
    });
  }

  function submitText(submit: boolean) {
    if (!text) return;
    send({ type: "type", text, submit });
    setText("");
  }

  return (
    <div className="overflow-hidden rounded-md border border-black/10 bg-white">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-4 py-2.5 text-sm font-medium text-black/70 hover:bg-black/[0.03]"
      >
        <span className="flex items-center gap-2">
          <Eye className="h-4 w-4" />
          {needsHuman ? "Browser — your turn" : "Watch the browser live"}
        </span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {open && (
        <div className="space-y-3 border-t border-black/10 p-3">
          {!frame ? (
            <div className="flex h-40 items-center justify-center gap-2 text-sm text-black/40">
              {finished ? (
                "The browser session has ended."
              ) : (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Waiting for the browser…
                </>
              )}
            </div>
          ) : (
            <>
              <p className="truncate text-xs text-black/40">{frame.url}</p>
              <div className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={imgRef}
                  src={`data:image/jpeg;base64,${frame.image}`}
                  alt="Live view of the agent's browser"
                  onClick={onTap}
                  draggable={false}
                  className={`block w-full select-none rounded border border-black/10 ${interactive ? "cursor-pointer" : ""} ${
                    interactive ? "" : "opacity-90"
                  }`}
                />
                {ripple && (
                  <span
                    key={ripple.k}
                    className="pointer-events-none absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 animate-ping rounded-full bg-accent/50"
                    style={{ left: ripple.x, top: ripple.y }}
                  />
                )}
              </div>
            </>
          )}

          {interactive && frame && (
            <div className="space-y-2">
              <p className="flex items-start gap-1.5 text-xs text-black/60">
                <MousePointerClick className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Tap the page above to click (e.g. the CAPTCHA checkbox or its images). Use the box below to type into a
                field you have tapped.
              </p>
              <div className="flex gap-2">
                <div className="relative min-w-0 flex-1">
                  <Keyboard className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-black/30" />
                  <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitText(true);
                    }}
                    placeholder="Type text, then press Enter"
                    maxLength={300}
                    autoComplete="off"
                    className="w-full rounded-md border border-black/15 py-2 pl-8 pr-2 text-sm"
                  />
                </div>
                <button
                  onClick={() => submitText(false)}
                  className="rounded-md border border-black/15 px-3 text-sm hover:bg-black/5"
                >
                  Type
                </button>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                {(["Enter", "Tab", "Backspace"] as const).map((k) => (
                  <button key={k} onClick={() => send({ type: "key", key: k })} className="rounded border border-black/15 px-2.5 py-1 hover:bg-black/5">
                    {k}
                  </button>
                ))}
                <button onClick={() => send({ type: "scroll", dy: -400 })} className="rounded border border-black/15 px-2.5 py-1 hover:bg-black/5">
                  Scroll up
                </button>
                <button onClick={() => send({ type: "scroll", dy: 400 })} className="rounded border border-black/15 px-2.5 py-1 hover:bg-black/5">
                  Scroll down
                </button>
              </div>
            </div>
          )}

          {needsHuman && !interactive && frame && (
            <p className="text-xs text-black/50">
              The browser is no longer waiting for you (the wait timed out). Use Resume to try again in a new browser.
            </p>
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
