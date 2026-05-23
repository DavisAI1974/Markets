#!/usr/bin/env python3
"""Tiny mock backend for markets-watch frontend dev preview.
Serves the minimal /api/* surface the UI calls. Numbers mirror the
markets_mockup.html reference so screenshots can be diffed visually.

Run: python mock_backend.py  (listens on 127.0.0.1:8000)
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Anchor at current wall clock minus a few seconds so "last hit … 12s ago"
# stays small. We rebuild on each request so "ago" doesn't drift during the
# session.
def _anchor():
    return int(time.time()) - 8

# realized_vol is a decimal fraction (UI displays as fraction*10000 bp).
# mean_dipole is a signed unit value. confidence is 0..1 (unadjusted);
# adjusted_confidence is confidence * cross_venue_multiplier, clipped to 1.
# notes is a list[str] to match the real RegimeStatus dataclass.
STATUSES = [
    {"asset":"BTC","venue":"coinbase","regime":"WHALE_UP",
     "confidence":0.74,"adjusted_confidence":0.82,"cross_venue_multiplier":1.1,
     "mean_dipole":0.412,"realized_vol":0.00073,
     "last_update_utc":_anchor()+8,
     "chunk_buy_volume":12.4,"chunk_sell_volume":3.2,"chunk_n_trades":87,
     "current_price":106847.20,"current_bid":106847.10,"current_ask":106847.30,
     "last_aggressor":"buy",
     "notes":["single dominant buyer, persistent positive H_a since 13:18"]},

    {"asset":"BTC","venue":"bybit","regime":"WHALE_UP",
     "confidence":0.72,"adjusted_confidence":0.79,"cross_venue_multiplier":1.1,
     "mean_dipole":0.388,"realized_vol":0.00069,
     "last_update_utc":_anchor()+11,
     "chunk_buy_volume":18.6,"chunk_sell_volume":5.1,"chunk_n_trades":124,
     "current_price":106851.45,"current_bid":106851.20,"current_ask":106851.70,
     "last_aggressor":"buy",
     "notes":[]},

    {"asset":"BTC","venue":"kraken","regime":"EQUILIBRIUM_TWO_SIDED",
     "confidence":0.78,"adjusted_confidence":0.71,"cross_venue_multiplier":0.5,
     "mean_dipole":0.041,"realized_vol":0.00042,
     "last_update_utc":_anchor()+14,
     "chunk_buy_volume":4.2,"chunk_sell_volume":4.4,"chunk_n_trades":58,
     "current_price":106839.00,"current_bid":106838.50,"current_ask":106839.60,
     "last_aggressor":"buy",
     "notes":[]},

    {"asset":"ETH","venue":"coinbase","regime":"HERD_DOWN",
     "confidence":0.80,"adjusted_confidence":0.88,"cross_venue_multiplier":1.1,
     "mean_dipole":-0.527,"realized_vol":0.00148,
     "last_update_utc":_anchor()-9,
     "chunk_buy_volume":4.1,"chunk_sell_volume":14.8,"chunk_n_trades":156,
     "current_price":3198.04,"current_bid":3197.95,"current_ask":3198.10,
     "last_aggressor":"sell",
     "notes":["broad-based sell pressure across many small orders"]},

    {"asset":"ETH","venue":"kraken","regime":"HERD_DOWN",
     "confidence":0.76,"adjusted_confidence":0.84,"cross_venue_multiplier":1.1,
     "mean_dipole":-0.491,"realized_vol":0.00131,
     "last_update_utc":_anchor()-6,
     "chunk_buy_volume":3.7,"chunk_sell_volume":13.1,"chunk_n_trades":142,
     "current_price":3197.86,"current_bid":3197.78,"current_ask":3197.95,
     "last_aggressor":"sell",
     "notes":[]},

    {"asset":"ETH","venue":"bybit","regime":"HERD_DOWN",
     "confidence":0.74,"adjusted_confidence":0.81,"cross_venue_multiplier":1.1,
     "mean_dipole":-0.462,"realized_vol":0.00124,
     "last_update_utc":_anchor()-4,
     "chunk_buy_volume":5.4,"chunk_sell_volume":15.7,"chunk_n_trades":188,
     "current_price":3198.22,"current_bid":3198.14,"current_ask":3198.30,
     "last_aggressor":"sell",
     "notes":[]},
]

BARS_BTC = [
    (0, 12.4, 3.2, 87, 106847.20, "buy"),
    (1, 8.1, 11.6, 102, 106782.10, "sell"),
    (2, 4.5, 9.8, 64, 106755.40, "sell"),
    (3, 6.2, 5.1, 71, 106791.20, "buy"),
    (4, 9.7, 4.3, 89, 106820.50, "buy"),
    (5, 5.4, 8.2, 78, 106758.80, "sell"),
]
BARS_ETH = [
    (0, 4.1, 14.8, 156, 3198.04, "sell"),
    (1, 3.4, 9.7, 118, 3195.10, "sell"),
    (2, 2.9, 8.3, 96, 3192.40, "sell"),
    (3, 4.5, 6.0, 84, 3196.20, "sell"),
    (4, 3.8, 5.5, 77, 3199.10, "sell"),
    (5, 2.6, 7.1, 69, 3190.80, "sell"),
]

def build_signals():
    now = _anchor()
    return [
        {"signal_id":"mock-btc-bybit-whale","asset":"BTC","venue":"bybit","regime":"WHALE_UP",
         "confidence":0.72,"adjusted_confidence":0.79,"cross_venue_multiplier":1.1,
         "mean_dipole":0.388,"realized_vol":0.00069,"chunk_volume":23.7,
         "notes":[],"playbook":"Piggyback only if early; watch for exhaustion when the buyer finishes.",
         "timestamp_utc":now-35,"chunk_window":[now-360,now],
         "chunk_buy_volume":18.6,"chunk_sell_volume":5.1,"chunk_n_trades":124,
         "current_price":106851.45,"current_bid":106851.20,"current_ask":106851.70,
         "last_aggressor":"buy","event_label":"Whale buyer detected",
         "outcome_status":"pending"},
        {"signal_id":"mock-eth-bybit-herd","asset":"ETH","venue":"bybit","regime":"HERD_DOWN",
         "confidence":0.74,"adjusted_confidence":0.81,"cross_venue_multiplier":1.1,
         "mean_dipole":-0.462,"realized_vol":0.00124,"chunk_volume":21.1,
         "notes":[],"playbook":"Do not catch the first break. Wait for the cascade to slow before fading.",
         "timestamp_utc":now-110,"chunk_window":[now-470,now-110],
         "chunk_buy_volume":5.4,"chunk_sell_volume":15.7,"chunk_n_trades":188,
         "current_price":3198.22,"current_bid":3198.14,"current_ask":3198.30,
         "last_aggressor":"sell","event_label":"Herd selling",
         "outcome_status":"resolved","outcome_realized_bps":12.4},
        {"signal_id":"mock-btc-kraken-equilibrium","asset":"BTC","venue":"kraken","regime":"EQUILIBRIUM_TWO_SIDED",
         "confidence":0.78,"adjusted_confidence":0.71,"cross_venue_multiplier":0.5,
         "mean_dipole":0.041,"realized_vol":0.00042,"chunk_volume":8.6,
         "notes":[],"playbook":"No clear directional edge. Watch for a break from two-sided flow.",
         "timestamp_utc":now-220,"chunk_window":[now-580,now-220],
         "chunk_buy_volume":4.2,"chunk_sell_volume":4.4,"chunk_n_trades":58,
         "current_price":106839.00,"current_bid":106838.50,"current_ask":106839.60,
         "last_aggressor":"buy","event_label":"Equilibrium",
         "outcome_status":"pending"},
    ]

def build_practice_trades():
    now = _anchor()
    return [
        {"intent_id":"mock-open-btc","asset":"BTC","venue":"bybit","side":"buy","qty":0.015,
         "status":"open","fill_price":106851.70,"mark_price":106872.40,
         "unrealized_pnl_usd":0.31,"fees_usd":4.01,"ts_utc":now-260,
         "note":"practice whale-buyer entry"},
        {"intent_id":"mock-closed-eth","asset":"ETH","venue":"bybit","side":"sell","qty":0.45,
         "status":"closed","fill_price":3198.14,"exit_price":3193.80,
         "realized_pnl_usd":1.95,"fees_usd":7.19,"ts_utc":now-1400,"exit_ts_utc":now-920,
         "note":"herd selling fade drill"},
    ]

def build_drift_alerts():
    now = _anchor()
    return [
        {"id":"mock-drift-1","type":"edge_strengthen","key":"BTC/Bybit/WHALE_UP",
         "summary":"BTC/Bybit whale-buyer edge strengthening across the last samples.",
         "abs_r_trend":[0.31,0.38,0.46],"ts_utc":now-75},
        {"id":"mock-drift-2","type":"sample_milestone","key":"ETH/Bybit/HERD_DOWN",
         "summary":"ETH/Bybit herd-selling sample crossed validation milestone.",
         "milestone":"50 samples","ts_utc":now-240},
    ]

def build_bars(asset):
    rows = BARS_BTC if asset == "BTC" else BARS_ETH
    is_btc = asset == "BTC"
    offset = 0.10 if is_btc else 0.05
    out = []
    for dt, buy, sell, trades, price, agg in rows:
        out.append({
            "ts": _anchor() - dt * 60,
            "buy_volume": buy, "sell_volume": sell,
            "n_trades": trades, "price": price,
            "bid": round(price - offset, 4), "ask": round(price + offset, 4),
            "last_aggressor": agg,
        })
    return list(reversed(out))

class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/status":
            return self._json({"statuses": STATUSES})
        if path.startswith("/api/chart/") or path.startswith("/api/tape/"):
            parts = path.strip("/").split("/")
            asset = parts[2] if len(parts) >= 3 else "BTC"
            return self._json({"data": build_bars(asset)})
        if path == "/api/signals":
            return self._json({"signals": build_signals()})
        if path.startswith("/api/signal/"):
            signal_id = path.strip("/").split("/")[-1]
            sig = next((s for s in build_signals() if s["signal_id"] == signal_id), build_signals()[0])
            return self._json({"signal": sig, "chart": build_bars(sig["asset"])})
        if path == "/api/drift-alerts":
            return self._json({"alerts": build_drift_alerts()})
        if path == "/api/stats":
            return self._json({
                "n_signals": 18,
                "cross_venue_confirmed": 12,
                "cross_venue_disagreed": 3,
                "avg_adjusted_confidence": 0.78,
                "by_regime": {"WHALE_UP": 7, "HERD_DOWN": 6, "EQUILIBRIUM_TWO_SIDED": 3, "WHALE_DOWN": 2},
                "by_source": {"BTC-bybit": 6, "ETH-bybit": 5, "BTC-coinbase": 4, "BTC-kraken": 3},
                "outcomes": {
                    "resolved": 9, "pending": 4, "abandoned": 1,
                    "win_rate": 0.67, "total_realized_bps": 42.8, "avg_realized_bps": 4.8,
                    "by_source_pnl": {
                        "BTC-bybit": {"n": 4, "wins": 3, "total_bps": 21.6},
                        "ETH-bybit": {"n": 3, "wins": 2, "total_bps": 14.2},
                        "BTC-kraken": {"n": 2, "wins": 1, "total_bps": 7.0},
                    },
                },
            })
        if path.startswith("/api/regime_history/"):
            parts = path.strip("/").split("/")
            asset = parts[2] if len(parts) >= 3 else "BTC"
            return self._json({"history": [{"ts": _anchor() - i * 60, "regime": "WHALE_UP", "confidence": 0.7 + 0.01 * (i % 10)} for i in range(60)]})
        if path == "/api/practice-trades":
            trades = build_practice_trades()
            return self._json({
                "trades": trades,
                "n_open": sum(1 for t in trades if t["status"] == "open"),
                "n_closed": sum(1 for t in trades if t["status"] == "closed"),
                "total_realized_pnl_usd": sum(t.get("realized_pnl_usd", 0) for t in trades if t["status"] == "closed"),
                "win_rate": 1.0,
            })
        if path == "/api/push/vapid-public-key":
            return self._json({"key": ""})
        if path == "/api/stream":
            # SSE — keep open with a single comment so EventSource doesn't error-loop
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                # Block forever so connection stays open
                while True:
                    time.sleep(15)
                    try:
                        self.wfile.write(b"event: heartbeat\ndata: {}\n\n")
                        self.wfile.flush()
                    except Exception:
                        break
            except Exception:
                pass
            return
        self._json({"error": "not found"}, status=404)

    def do_POST(self):
        self._json({"ok": True})

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    print("mock backend on http://127.0.0.1:8000", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
