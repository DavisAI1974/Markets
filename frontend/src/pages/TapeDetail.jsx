import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useStore } from "../store.js";
import { fetchStatus } from "../api.js";
import LiveTape from "../components/LiveTape.jsx";

export default function TapeDetail() {
  const { asset, venue } = useParams();

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-3">
        <Link to="/" className="text-sm text-slate-400 hover:text-slate-100">
          &lsaquo; back to live
        </Link>
      </div>
      <TapeDetailBody asset={asset} venue={venue} />
    </div>
  );
}

function TapeDetailBody({ asset, venue }) {
  const storeStatus = useStore((s) =>
    (s.statuses || []).find((x) => x.asset === asset && x.venue === venue)
  );
  const [localStatus, setLocalStatus] = useState(null);
  const status = storeStatus || localStatus;

  useEffect(() => {
    if (storeStatus) {
      setLocalStatus(null);
      return undefined;
    }

    let cancelled = false;
    fetchStatus()
      .then((j) => {
        if (cancelled) return;
        const match = (j.statuses || []).find((x) => x.asset === asset && x.venue === venue);
        setLocalStatus(match || null);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [asset, venue, storeStatus]);

  const regime = status?.regime;

  return <LiveTape asset={asset} venue={venue} regime={regime} status={status} />;
}
