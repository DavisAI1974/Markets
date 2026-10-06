# Fetch the PINNED llama.cpp release asset and the PINNED official Granite GGUF into GRANITE_DIR, verifying each sha256
# against knowledge/GRANITE_MEETING_RUNTIME_V1.json ON EVERY INVOCATION, cached or freshly downloaded (Codex finding,
# 2026-10-06: the archive check sat inside the download-only branch and a cached GGUF was hashed but never compared).
# Every pin is an explicit blank until Greg or the integrating session fills it from the official sources; this script
# REFUSES while any pin is null, so nothing is guessed or fetched blind. A retained file that differs from its pin is
# REFUSED AND LEFT IN PLACE (named in the refusal), never replaced or re-downloaded over; an existing extraction is
# verified, never overwritten. LLAMA_SERVER / GGUF_MODEL are emitted only after every verification passed.
# Not run anywhere yet (no install authorized). Inputs: CODE_ROOT, GRANITE_DIR (default /opt/frankie-box/granite).
set -eu
: "${CODE_ROOT:?checkout required}"
GRANITE_DIR="${GRANITE_DIR:-/opt/frankie-box/granite}"
CONFIG="$CODE_ROOT/research/kalshi/frankie_boss/knowledge/GRANITE_MEETING_RUNTIME_V1.json"
[ -f "$CONFIG" ] || { echo "no runtime config at $CONFIG" >&2; exit 2; }
pin() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1]))["pins"].get(sys.argv[2]); print("" if v is None else v)' "$CONFIG" "$1"; }
REPO="$(pin model_repository)"; FILE="$(pin model_file)"; MODEL_SHA="$(pin model_sha256)"
REL="$(pin llama_cpp_release)"; ASSET="$(pin llama_cpp_asset)"; ASSET_SHA="$(pin llama_cpp_sha256)"; SERVER_SHA="$(pin llama_server_sha256)"
for v in REPO FILE MODEL_SHA REL ASSET ASSET_SHA SERVER_SHA; do
  eval val="\${$v}"
  [ -n "$val" ] || { echo "refused: pin $v is an explicit blank in GRANITE_MEETING_RUNTIME_V1.json; fill the official value first" >&2; exit 3; }
done
# verify FILE PIN LABEL: the file's sha256 must equal the pin; otherwise refuse, naming both, and leave the file as it is.
verify() {
  actual="$(sha256sum "$1" | cut -c1-64)"
  [ "$actual" = "$2" ] || { echo "refused: $3 at $1 has sha256 $actual, pin is $2; the retained file is left in place, not replaced (remove it by hand to re-fetch)" >&2; exit 4; }
}
mkdir -p "$GRANITE_DIR"
cd "$GRANITE_DIR"
# 1. llama.cpp archive: a tagged release asset of github.com/ggml-org/llama.cpp. Downloaded only when absent (to .part,
#    verified, then moved); the retained archive is verified on EVERY run, before anything is extracted from it.
if [ ! -f "$ASSET" ]; then
  curl -fsSL -o "$ASSET.part" "https://github.com/ggml-org/llama.cpp/releases/download/$REL/$ASSET"
  echo "$ASSET_SHA  $ASSET.part" | sha256sum -c - >/dev/null 2>&1 || { rm -f "$ASSET.part"; echo "refused: downloaded llama.cpp asset sha256 differs from the pin; the partial file was discarded" >&2; exit 4; }
  mv "$ASSET.part" "$ASSET"
fi
verify "$ASSET" "$ASSET_SHA" "llama.cpp archive"
# 2. extraction: only into an ABSENT top directory. An existing extraction (complete or partial) is never overwritten by
#    re-extracting over it; it is verified below against the pinned file manifest and refused if it differs.
case "$ASSET" in
  *.zip) TOP="$(unzip -Z1 "$ASSET" | head -n 1 | cut -d/ -f1)";;
  *.tar.gz|*.tgz) TOP="$(tar -tzf "$ASSET" | head -n 1 | cut -d/ -f1)";;
  *) echo "unknown asset format $ASSET" >&2; exit 4;;
esac
[ -n "$TOP" ] && [ "$TOP" != "." ] || { echo "refused: the archive has no single top directory to extract into" >&2; exit 4; }
if [ ! -e "$GRANITE_DIR/$TOP" ]; then
  case "$ASSET" in *.zip) unzip -q "$ASSET";; *) tar -xzf "$ASSET";; esac
fi
SERVER="$GRANITE_DIR/$TOP/llama-server"
[ -f "$SERVER" ] || { echo "refused: llama-server not found at $SERVER; a retained extraction is not replaced (remove $GRANITE_DIR/$TOP by hand to re-extract)" >&2; exit 4; }
# 3. the official GGUF from the pinned Hugging Face repository. Downloaded only when absent (to .part, verified, moved);
#    the retained model is verified on EVERY run, downloaded or cached, before it is reported as usable.
if [ ! -f "$FILE" ]; then
  curl -fsSL -o "$FILE.part" "https://huggingface.co/$REPO/resolve/main/$FILE"
  echo "$MODEL_SHA  $FILE.part" | sha256sum -c - >/dev/null 2>&1 || { rm -f "$FILE.part"; echo "refused: downloaded model sha256 differs from the pin; the partial file was discarded" >&2; exit 4; }
  mv "$FILE.part" "$FILE"
fi
verify "$FILE" "$MODEL_SHA" "Granite GGUF"
# 4. the provenance chain: the archive hash covers the FETCH only. The installed runtime is llama-server plus the shared
#    libraries beside it, so every extracted file is verified against the pinned manifest (pins.llama_cpp_files) and the
#    binary against pins.llama_server_sha256; the same check the Python gate repeats at every meeting. A mismatch refuses
#    and nothing is replaced. The provenance receipt is written only after every check above passed.
python3 - "$CONFIG" "$SERVER" "$REL" "$ASSET" "$ASSET_SHA" "$GRANITE_DIR/$FILE" "$MODEL_SHA" <<'EOF2'
import hashlib, json, os, sys
config, server, release, asset, asset_sha, model, model_sha = sys.argv[1:8]
pins = json.load(open(config))['pins']
manifest, server_sha = pins.get('llama_cpp_files') or {}, pins.get('llama_server_sha256')
if not manifest or not server_sha:
    sys.exit('refused: pins llama_cpp_files / llama_server_sha256 are explicit blanks; the extracted runtime cannot be verified')
root = os.path.dirname(server)
digest = lambda path: hashlib.sha256(open(path, 'rb').read()).hexdigest()
bad = [name for name, sha in sorted(manifest.items())
       if not os.path.isfile(os.path.join(root, name)) or digest(os.path.join(root, name)) != sha]
if bad:
    sys.exit('refused: extracted files differ from pin llama_cpp_files (left in place, not replaced): %s' % ', '.join(bad))
if digest(server) != server_sha:
    sys.exit('refused: llama-server sha256 differs from pin llama_server_sha256 (left in place, not replaced)')
provenance = dict(schema='FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1', release=release, asset=asset, archive_sha256=asset_sha,
                  server=server, server_sha256=server_sha, files_verified=len(manifest),
                  model=model, model_sha256=model_sha, verified_every_run=True, host_cpus=os.cpu_count())
with open(os.path.join(root, 'provenance.json'), 'w') as handle:
    json.dump(provenance, handle, indent=1, sort_keys=True)
print(json.dumps(provenance, sort_keys=True))
EOF2
echo "LLAMA_SERVER=$SERVER"
echo "GGUF_MODEL=$GRANITE_DIR/$FILE"
