# Signa import verification

`file-manifest.json` lists every final path with size, sha256, git blob sha1, and batch.
`verify_manifest.py` checks the tree (`--manifest`, `--root`, `--batch N` or `A-B`) and leftover `*.xfer-NN` chunks.
`batches.json` lists the 61 archives and any transport_reassembly commands.
