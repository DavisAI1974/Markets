# Fetch the PINNED llama.cpp release asset and the PINNED official Granite GGUF into GRANITE_DIR, verifying each sha256
# against knowledge/GRANITE_MEETING_RUNTIME_V1.json. Every pin is an explicit blank until Greg or the integrating session
# fills it from the official sources; this script REFUSES while any pin is null, so nothing is guessed or fetched blind.
# Not run anywhere yet (no install authorized). Inputs: CODE_ROOT, GRANITE_DIR (default /opt/frankie-box/granite).
set -eu
: "${CODE_ROOT:?checkout required}"
GRANITE_DIR="${GRANITE_DIR:-/opt/frankie-box/granite}"
CONFIG="$CODE_ROOT/research/kalshi/frankie_boss/knowledge/GRANITE_MEETING_RUNTIME_V1.json"
[ -f "$CONFIG" ] || { echo "no runtime config at $CONFIG" >&2; exit 2; }
pin() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1]))["pins"].get(sys.argv[2]); print("" if v is None else v)' "$CONFIG" "$1"; }
REPO="$(pin model_repository)"; FILE="$(pin model_file)"; MODEL_SHA="$(pin model_sha256)"
REL="$(pin llama_cpp_release)"; ASSET="$(pin llama_cpp_asset)"; ASSET_SHA="$(pin llama_cpp_sha256)"
for v in REPO FILE MODEL_SHA REL ASSET ASSET_SHA; do
  eval val="\${$v}"
  [ -n "$val" ] || { echo "refused: pin $v is an explicit blank in GRANITE_MEETING_RUNTIME_V1.json; fill the official value first" >&2; exit 3; }
done
mkdir -p "$GRANITE_DIR"
cd "$GRANITE_DIR"
# llama.cpp: a tagged release asset of github.com/ggml-org/llama.cpp, verified by the pinned sha256 before extraction.
if [ ! -f "$ASSET" ]; then
  curl -fsSL -o "$ASSET.part" "https://github.com/ggml-org/llama.cpp/releases/download/$REL/$ASSET"
  echo "$ASSET_SHA  $ASSET.part" | sha256sum -c - >/dev/null || { rm -f "$ASSET.part"; echo "llama.cpp asset sha256 differs from the pin" >&2; exit 4; }
  mv "$ASSET.part" "$ASSET"
fi
case "$ASSET" in *.zip) unzip -oq "$ASSET";; *.tar.gz|*.tgz) tar -xzf "$ASSET";; *) echo "unknown asset format $ASSET" >&2; exit 4;; esac
SERVER="$(find "$GRANITE_DIR" -type f -name llama-server | head -n 1)"
[ -n "$SERVER" ] || { echo "llama-server not found in the extracted asset" >&2; exit 4; }
# The provenance chain: the archive hash above covers the FETCH only. The installed runtime is llama-server plus the
# shared libraries beside it, so every extracted file is verified against the pinned manifest (pins.llama_cpp_files) and
# the binary against pins.llama_server_sha256; the same check the Python gate repeats at every meeting. A mismatch refuses.
python3 - "$CONFIG" "$SERVER" "$REL" "$ASSET" "$ASSET_SHA" <<'EOF2'
import hashlib, json, os, sys
config, server, release, asset, asset_sha = sys.argv[1:6]
pins = json.load(open(config))['pins']
manifest, server_sha = pins.get('llama_cpp_files') or {}, pins.get('llama_server_sha256')
if not manifest or not server_sha:
    sys.exit('refused: pins llama_cpp_files / llama_server_sha256 are explicit blanks; the extracted runtime cannot be verified')
root = os.path.dirname(server)
digest = lambda path: hashlib.sha256(open(path, 'rb').read()).hexdigest()
bad = [name for name, sha in sorted(manifest.items())
       if not os.path.isfile(os.path.join(root, name)) or digest(os.path.join(root, name)) != sha]
if bad:
    sys.exit('refused: extracted files differ from pin llama_cpp_files: %s' % ', '.join(bad))
if digest(server) != server_sha:
    sys.exit('refused: llama-server sha256 differs from pin llama_server_sha256')
provenance = dict(schema='FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1', release=release, asset=asset, archive_sha256=asset_sha,
                  server=server, server_sha256=server_sha, files_verified=len(manifest), host_cpus=os.cpu_count())
with open(os.path.join(root, 'provenance.json'), 'w') as handle:
    json.dump(provenance, handle, indent=1, sort_keys=True)
print(json.dumps(provenance, sort_keys=True))
EOF2
# The official GGUF, from the pinned Hugging Face repository, verified by the pinned sha256.
if [ ! -f "$FILE" ]; then
  curl -fsSL -o "$FILE.part" "https://huggingface.co/$REPO/resolve/main/$FILE"
  echo "$MODEL_SHA  $FILE.part" | sha256sum -c - >/dev/null || { rm -f "$FILE.part"; echo "model sha256 differs from the pin" >&2; exit 4; }
  mv "$FILE.part" "$FILE"
fi
python3 - "$SERVER" "$GRANITE_DIR/$FILE" <<'EOF'
import hashlib, json, sys
for label, path in zip(('llama-server', 'model'), sys.argv[1:3]):
    print(json.dumps(dict(item=label, path=path, sha256=hashlib.sha256(open(path, 'rb').read()).hexdigest())))
EOF
echo "LLAMA_SERVER=$SERVER"
echo "GGUF_MODEL=$GRANITE_DIR/$FILE"
