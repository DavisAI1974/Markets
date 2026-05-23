export const MARKET_READ_LABELS = {
  EQUILIBRIUM_TWO_SIDED: "Equilibrium",
  WHALE_UP: "Whale buyer",
  WHALE_DOWN: "Whale seller",
  WHALE_NASCENT_UP: "Buy pressure forming",
  WHALE_NASCENT_DOWN: "Sell pressure forming",
  HERD_UP: "Herd buying",
  HERD_DOWN: "Herd selling",
  CROSS_VENUE_WHALE_HERD_UP: "Whale to herd buying",
  CROSS_VENUE_HERD_WHALE_UP: "Herd and whale buying",
  CROSS_VENUE_WHALE_HERD_DOWN: "Whale to herd selling",
  CROSS_VENUE_HERD_WHALE_DOWN: "Herd and whale selling",
  WASH_PAIRED: "Suspect flow",
  WASH_HAWKES: "Suspect flow",
  DEPLETED: "Quiet market",
  UNKNOWN: "Watching",
};

export const MARKET_READ_HEADLINES = {
  WHALE_UP: "Whale buyer detected",
  WHALE_DOWN: "Whale seller detected",
  WHALE_NASCENT_UP: "Buy pressure forming",
  WHALE_NASCENT_DOWN: "Sell pressure forming",
  HERD_UP: "Herd buying",
  HERD_DOWN: "Herd selling",
  CROSS_VENUE_WHALE_HERD_UP: "Cross-venue whale to herd buying",
  CROSS_VENUE_HERD_WHALE_UP: "Cross-venue herd and whale buying",
  CROSS_VENUE_WHALE_HERD_DOWN: "Cross-venue whale to herd selling",
  CROSS_VENUE_HERD_WHALE_DOWN: "Cross-venue herd and whale selling",
  WASH_PAIRED: "Wash pattern - skip",
  WASH_HAWKES: "Wash pattern - skip",
  EQUILIBRIUM_TWO_SIDED: "Equilibrium",
  DEPLETED: "Market quiet",
  UNKNOWN: "Unclassified",
};

export const MARKET_STRUCTURE_COPY = {
  WHALE_UP: "Concentrated buyer: a big player is lifting offers. Piggyback early, but watch for exhaustion when that buyer finishes.",
  WHALE_DOWN: "Concentrated seller: a big player is hitting bids. Pressure can end fast when their inventory is done.",
  WHALE_NASCENT_UP: "Early buyer pressure: treat it as forming, not confirmed. Wait for more volume or venue confirmation before sizing up.",
  WHALE_NASCENT_DOWN: "Early seller pressure: treat it as forming, not confirmed. Wait for persistence before leaning into it.",
  HERD_UP: "Broad crowd buying: many participants are moving together. Momentum can run, but overshoots can snap back.",
  HERD_DOWN: "Broad crowd selling: many participants are rushing the same way. Avoid catching it until the cascade slows.",
  CROSS_VENUE_WHALE_HERD_UP: "Big-player buying is spilling into crowd buying across venues. Momentum can accelerate, but exhaustion matters.",
  CROSS_VENUE_HERD_WHALE_UP: "Crowd buying and big-player buying are aligned across venues. Treat the move as stronger than a single-venue read.",
  CROSS_VENUE_WHALE_HERD_DOWN: "Big-player selling is spilling into crowd selling across venues. Stay alert for a cascade, then exhaustion.",
  CROSS_VENUE_HERD_WHALE_DOWN: "Crowd selling and big-player selling are aligned across venues. Avoid fighting it until pressure slows.",
  EQUILIBRIUM_TWO_SIDED: "Two-sided flow: buyers and sellers are pushing back. No clear directional edge yet.",
  WASH_PAIRED: "Artificial-looking flow: price discovery is suspect. Skip it until cleaner participation returns.",
  WASH_HAWKES: "Artificial-looking flow: price discovery is suspect. Skip it until cleaner participation returns.",
  DEPLETED: "Quiet market: not enough flow to trust the read. Wait for activity to return.",
  UNKNOWN: "Watching: the tape has not formed a clean market read yet.",
};

export function getReadQualityLabel(statusOrRegime) {
  const status = typeof statusOrRegime === "string" ? { regime: statusOrRegime } : (statusOrRegime || {});
  const regime = status.regime || "UNKNOWN";

  if (regime === "EQUILIBRIUM_TWO_SIDED") return "Two-sided";
  if (regime === "WHALE_UP") return "Clean buyer";
  if (regime === "WHALE_DOWN") return "Clean seller";
  if (regime === "WHALE_NASCENT_UP" || regime === "WHALE_NASCENT_DOWN") return "Forming";
  if (regime === "HERD_UP" || regime === "HERD_DOWN") return "Crowd";
  if (regime.startsWith("CROSS_VENUE_")) return "Confirmed";
  if (regime.startsWith("WASH")) return "Noisy";
  if (regime === "DEPLETED") return "Thin";

  const adjusted = status.adjusted_confidence ?? status.confidence ?? 0;
  if (adjusted >= 0.7) return "Strong";
  if (adjusted >= 0.45) return "Mixed";
  return "Incomplete";
}

export function getMarketReadLabel(regime) {
  return MARKET_READ_LABELS[regime] || MARKET_READ_LABELS.UNKNOWN;
}

export function getMarketReadHeadline(regime) {
  return MARKET_READ_HEADLINES[regime] || "Market read";
}

export function getMarketStructureCopy(regime) {
  return MARKET_STRUCTURE_COPY[regime] || MARKET_STRUCTURE_COPY.UNKNOWN;
}
