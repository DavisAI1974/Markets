import React from "react";
import { useParams, Link } from "react-router-dom";
import SignalDetailBody from "../components/SignalDetailBody.jsx";

export default function SignalDetail() {
  const { id } = useParams();
  return (
    <div className="space-y-4">
      <Link to="/signals" className="text-xs text-slate-400 hover:text-slate-200">
        ← back to feed
      </Link>
      <SignalDetailBody id={id} />
    </div>
  );
}
