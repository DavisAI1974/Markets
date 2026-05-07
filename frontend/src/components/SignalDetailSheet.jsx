import React, { useEffect, useRef, useState } from "react";
import { useStore } from "../store.js";
import SignalDetailBody from "./SignalDetailBody.jsx";

/**
 * Bottom-sheet overlay rendering SignalDetailBody. Triggered when
 * store.openSignalDetailId is set. Mobile-native feel:
 *
 *   - Slide-up animation from the bottom
 *   - Tap the backdrop to dismiss
 *   - Swipe down on the handle (or anywhere in the top bar) to dismiss
 *   - Esc key dismisses
 *   - Body content scrolls within the sheet; backdrop locks page scroll
 *
 * Direct URLs (/signal/:id) still render the full-page SignalDetail
 * route — this sheet is the in-app overlay path that avoids losing
 * context when tapping a signal card from the feed.
 */

const DISMISS_DRAG_PX = 90;       // drag this far down → release dismisses
const SHEET_VH = 92;               // sheet covers this much of viewport height

export default function SignalDetailSheet() {
  const id = useStore((s) => s.openSignalDetailId);
  const close = useStore((s) => s.closeSignalSheet);
  const [dragY, setDragY] = useState(0);
  const startY = useRef(null);
  const closing = useRef(false);

  // Esc key dismiss + lock body scroll while open
  useEffect(() => {
    if (!id) return;
    function onKey(e) { if (e.key === "Escape") close(); }
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [id, close]);

  // Reset drag state when the sheet opens
  useEffect(() => {
    if (id) { setDragY(0); closing.current = false; }
  }, [id]);

  if (!id) return null;

  function onTouchStart(e) {
    startY.current = e.touches[0].clientY;
    closing.current = false;
  }
  function onTouchMove(e) {
    if (startY.current == null) return;
    const dy = e.touches[0].clientY - startY.current;
    if (dy > 0) setDragY(dy);
  }
  function onTouchEnd() {
    if (dragY > DISMISS_DRAG_PX) {
      closing.current = true;
      close();
    } else {
      setDragY(0);
    }
    startY.current = null;
  }

  // Translate driven by drag; transition off during drag, on during
  // settle/dismiss for the spring-back / slide-down feel.
  const isDragging = startY.current != null;
  const transform = `translateY(${dragY}px)`;
  const transition = isDragging ? "none" : "transform 240ms cubic-bezier(0.32, 0.72, 0, 1)";

  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center"
      // Tap on the backdrop (not the sheet) to dismiss.
      onClick={(e) => { if (e.target === e.currentTarget) close(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-[fadeIn_200ms_ease-out]" />
      {/* Sheet */}
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-3xl bg-slate-950 border-t border-slate-700
                     rounded-t-2xl shadow-2xl flex flex-col animate-[slide-in-up_280ms_cubic-bezier(0.32,0.72,0,1)]"
        style={{
          height: `${SHEET_VH}vh`,
          transform,
          transition,
        }}
      >
        {/* Drag handle / top bar — touch events here drive dismiss-by-drag */}
        <div
          className="flex flex-col items-center pt-2 pb-1 cursor-grab select-none"
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
          onTouchCancel={onTouchEnd}
        >
          <div className="w-10 h-1.5 rounded-full bg-slate-600 mb-1" aria-hidden="true" />
          <div className="flex items-center justify-between w-full px-3 text-xs">
            <span className="text-slate-500">Signal detail</span>
            <button
              onClick={close}
              className="text-slate-400 hover:text-slate-100 px-2 py-0.5 text-base leading-none"
              aria-label="close signal detail"
            >
              ×
            </button>
          </div>
        </div>
        {/* Body — scrolls inside the sheet */}
        <div className="flex-1 overflow-y-auto px-4 pb-6 pt-2">
          <SignalDetailBody id={id} />
        </div>
      </div>
    </div>
  );
}
