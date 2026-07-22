"""
Quick test: does live MBO flow on your current Databento license?

Run:
    export DATABENTO_API_KEY="db-XXXXXXXX"   # your key from portal -> API keys
    python3 mbo_test.py

What you'll see:
  - Rows of MBO messages printing  -> MBO is entitled and flowing. Done.
  - An error mentioning permission / entitlement / license
                                   -> the license doesn't cover MBO yet.
  - Nothing at all                 -> market may be quiet/closed; try again
                                      during CME hours, or widen the symbol.
"""

import os
import sys

try:
    import databento as db
except ImportError:
    sys.exit("databento not installed. Run: pip3 install databento")

KEY = os.environ.get("DATABENTO_API_KEY")
if not KEY:
    sys.exit("Set DATABENTO_API_KEY first (see header of this file).")

client = db.Live(key=KEY)

# Front-month E-mini S&P via continuous symbology = always the active contract.
client.subscribe(
    dataset="GLBX.MDP3",   # CME Globex MDP 3.0
    schema="mbo",          # <-- L3, full order book (the thing you're testing)
    stype_in="continuous",
    symbols=["ES.c.0"],
)

print("Subscribed to MBO on GLBX.MDP3 (ES front month). Waiting for messages...\n")

count = 0
try:
    for record in client:
        print(record)
        count += 1
        if count >= 20:      # stop after 20 messages so it doesn't run forever
            print("\n--- MBO is flowing. 20 messages received, stopping. ---")
            break
except Exception as e:
    print(f"\n!!! Stream error (this usually tells us the license gap):\n{e}")
finally:
    client.stop()
