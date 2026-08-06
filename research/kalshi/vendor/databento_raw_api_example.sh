#!/usr/bin/env bash
# VENDOR REFERENCE - Databento official Raw API example (bash), pasted by Greg from
# databento.com docs 2026-07-20 (S100). NOT our integration path - we use their official
# Python client (databento.Live). Kept verbatim: it documents the live gateway's CRAM
# authentication handshake and session protocol, useful if a low-level collector is ever
# built on the live box. KEY placeholder intentional - never commit a real key.
set -e

KEY=YOUR_API_KEY

cram_response() {
    local cram=${1#cram=}
    local hash=$(echo -n "$cram|$KEY" | sha256sum | head -c 64)
    local resp=$hash-${KEY: -5}
    echo "auth=$resp|dataset=GLBX.MDP3|encoding=json|ts_out=1"
}

exec 3<>/dev/tcp/glbx-mdp3.lsg.databento.com/13000
trap 'exec 3>&-' EXIT

read version_str <&3
read cram <&3

response=$(cram_response $cram)

echo $response >&3
read success <&3

if ! [[ $success =~ "success=1" ]]; then
    echo "Authentication failed" >&2
    exit 2
fi

echo "schema=trades|stype_in=parent|symbols=ES.FUT" >&3
echo "start_session=1" >&3

timeout 20s cat <&3

# VARIANT (same tutorial, step 3 continued): only the subscribe line changes - any schema
# and symbol list can be requested the same way, e.g. 1-second OHLCV bars for two parents:
#   echo "schema=ohlcv-1s|stype_in=parent|symbols=ES.FUT,NQ.FUT" >&3
#   echo "start_session=1" >&3
#   timeout 10s cat <&3
# Live schemas therefore include ohlcv-1s server-side aggregation. Our NG canary stays on
# schema=trades (1s bars undersample the lag - standing rule); ohlcv-1s is noted as a
# bandwidth-saving option for slower-cadence live consumers.
