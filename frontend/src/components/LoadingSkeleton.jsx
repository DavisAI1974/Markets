import React from "react";

/**
 * Generic shimmering skeleton blocks. Use to give the UI shape during
 * the first few hundred milliseconds before SSE / fetch results arrive,
 * so the app doesn't look broken on mobile cold starts.
 */

export function SkeletonCard({ heightCls = "h-44" }) {
  return (
    <div
      className={`rounded-lg border border-slate-800 bg-slate-900/50 ${heightCls}
                    animate-pulse mb-3 overflow-hidden relative`}
    >
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-slate-800/50 to-transparent
                         animate-[shimmer_1.6s_infinite]" />
    </div>
  );
}

export function SkeletonLine({ widthCls = "w-3/4" }) {
  return (
    <div className={`h-3 rounded bg-slate-800 ${widthCls} animate-pulse mb-2`} />
  );
}

export function SkeletonBlock({ children }) {
  return <div className="animate-pulse">{children}</div>;
}

/**
 * Empty-state card. Render when an endpoint returned 0 items.
 *
 * Props:
 *   icon: React node (usually an emoji or small SVG)
 *   title: short headline
 *   body: secondary descriptive text
 *   action: optional ReactNode (e.g. a Link/button to encourage next step)
 */
export function EmptyState({ icon, title, body, action }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6 text-center">
      {icon && <div className="text-3xl mb-2 select-none">{icon}</div>}
      <div className="font-semibold text-slate-200 text-sm mb-1">{title}</div>
      {body && <div className="text-xs text-slate-400 leading-relaxed max-w-md mx-auto">{body}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
