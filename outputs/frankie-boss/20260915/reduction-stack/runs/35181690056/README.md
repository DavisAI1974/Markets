# Complete journal result archive

All result files are preserved in the authenticated encrypted parts listed in archive-manifest.json. Use the existing retained RSA private recipient key to unwrap the AES key with OAEP/SHA256; decrypt parts in order using their nonce and AAD, concatenate, verify archive SHA256, then extract the tar.gz. Raw market journal/checkpoint bytes and credentials are not public.
