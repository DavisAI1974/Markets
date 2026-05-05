import { useEffect, useRef, useState } from "react";

/**
 * Pull-to-refresh hook for mobile-installed PWAs.
 *
 * Wires touch events on a target element (or window). When the user is
 * scrolled to the top and pulls down past `threshold` px, the
 * `onRefresh` async callback fires once. Returns:
 *   { pulling, distance, refreshing }
 * which the caller can render as a small pull indicator (or ignore).
 *
 * Caveats:
 * - On iOS Safari the system rubber-band scroll fights for the gesture.
 *   We still get the touchstart/touchmove events; the visual elastic
 *   bounce is a no-op overlay, and we trigger refresh when the user
 *   releases past threshold.
 * - Listens passively; doesn't block native scroll.
 */
export function usePullToRefresh(onRefresh, { threshold = 64, enabled = true } = {}) {
  const [pulling, setPulling] = useState(false);
  const [distance, setDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef(0);
  const lastDistance = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    function onTouchStart(e) {
      if (window.scrollY > 0) return;
      startY.current = e.touches[0].clientY;
      setPulling(true);
    }
    function onTouchMove(e) {
      if (!pulling) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy > 0) {
        // dampen so it feels rubbery
        const damped = Math.min(dy * 0.6, threshold * 1.6);
        lastDistance.current = damped;
        setDistance(damped);
      } else {
        setDistance(0);
      }
    }
    async function onTouchEnd() {
      const fired = lastDistance.current >= threshold;
      setPulling(false);
      setDistance(0);
      lastDistance.current = 0;
      if (fired && !refreshing) {
        setRefreshing(true);
        try {
          await onRefresh();
        } finally {
          setRefreshing(false);
        }
      }
    }
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove",  onTouchMove,  { passive: true });
    window.addEventListener("touchend",   onTouchEnd,   { passive: true });
    window.addEventListener("touchcancel",onTouchEnd,   { passive: true });
    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove",  onTouchMove);
      window.removeEventListener("touchend",   onTouchEnd);
      window.removeEventListener("touchcancel",onTouchEnd);
    };
  }, [onRefresh, pulling, refreshing, threshold, enabled]);

  return { pulling, distance, refreshing };
}

/**
 * Visual indicator shell. Renders a small "pull to refresh" hint at
 * the top that grows + rotates as the user pulls. Pair with the hook
 * by spreading its return values.
 */
export function PullIndicator({ pulling, distance, refreshing, threshold = 64 }) {
  const ready = distance >= threshold;
  const visible = pulling || refreshing;
  if (!visible && distance === 0) return null;
  const angle = Math.min((distance / threshold) * 180, 360);
  return (
    <div
      style={{
        height: `${distance}px`,
        transition: pulling ? "none" : "height 200ms ease-out",
      }}
      className="flex items-center justify-center text-xs text-slate-400 overflow-hidden"
    >
      <span
        style={{ transform: `rotate(${refreshing ? 0 : angle}deg)` }}
        className={`inline-block transition-transform ${refreshing ? "animate-spin" : ""}`}
      >
        ↓
      </span>
      <span className="ml-2">
        {refreshing ? "Refreshing…" : ready ? "Release to refresh" : "Pull to refresh"}
      </span>
    </div>
  );
}
