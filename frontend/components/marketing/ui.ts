/** Shared class strings so every marketing button and section behaves the same way. */
export const BTN_BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold transition-colors";
export const BTN_PRIMARY = `${BTN_BASE} bg-accent-fill text-white hover:bg-accent-fill/90`;
export const BTN_SECONDARY = `${BTN_BASE} border border-line-strong bg-surface text-ink hover:bg-subtle`;
export const BTN_ON_DEEP = `${BTN_BASE} bg-white text-deep hover:bg-white/90`;
export const BTN_GHOST_ON_DEEP = `${BTN_BASE} border border-white/30 text-white hover:bg-white/10`;

export const CONTAINER = "mx-auto w-full max-w-[1120px] px-5 sm:px-8";
export const SECTION = "scroll-mt-20 py-16 sm:py-20 lg:py-28";
export const H2 = "font-display text-[clamp(1.8rem,3vw,3rem)] font-semibold leading-[1.15] tracking-tight";
export const EYEBROW = "text-xs font-semibold uppercase tracking-[0.14em] text-accent-strong";