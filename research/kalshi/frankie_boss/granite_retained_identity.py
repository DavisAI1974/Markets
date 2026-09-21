"""The retained Granite Pod's declared identities, in one place.

POD_ID is the Pod the retained observer, lifecycle and completion publisher act on. It changes only by
a migration receipt (granite_retained_migration_receipt.json) that chains the new Pod from the accepted
retained receipt; granite_retained_host.INFO_SHA256 pins the resulting retained info. Each request's
journal lives under retained-granite/<request_sha256>/<JOURNAL_GENERATION>/, so a new Pod or a new
reviewed bundle opens a new generation. HISTORICAL_GENERATION names the first migrated Pod's journal
before the bundle suffix existed; it is history and never moves.
"""
POD_ID = 'g7y3g2w1kor4l3'      # replacement prepared 2026-09-21 (run 35553732076); 8vqdacl5t61rjx and ycf4v6lmave6xw stranded on GPU-less hosts
BUNDLE_PREFIX = 'a004983e93b9'        # first 12 hex of the reviewed bundle sha256 (runs/20260919/reviewed-bootstrap-image-defaults-runtime.json)
JOURNAL_GENERATION = 'migration-' + POD_ID + '-' + BUNDLE_PREFIX
HISTORICAL_GENERATION = 'migration-ycf4v6lmave6xw'
