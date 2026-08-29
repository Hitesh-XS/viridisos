# Canon to ViridisOS integration

`tools/sync_canon_kernels.py` verifies the digest of a pinned public Viridis
Canon catalog and writes `runtime/canon_kernel_registry.json`. The registry
contains every public Canon record and gives each one an explicit disposition.

A record becomes `KERNEL_CANDIDATE` only when Canon marks it both
`status=verified` and `integrity=gate-passed`. Ingestion never activates a
runtime module, creates a customer-facing decision-tree branch, or grants
certificate authority. A separately reviewed binding in
`runtime/canon_kernel_bindings.json` is required to name a module and decision
tree path. Missing bindings stay `BACKLOG_NO_WRAPPER`; working Canon records stay
`BACKLOG_CANON_ADMISSION_REQUIRED`; quarantined records remain quarantined.

The HTTP service exposes the read-only result at `GET /research-kernels`. Module
execution and certification continue to use their existing A-1 through A-5
gates.

To refresh from an exact Canon checkout:

```sh
python3 tools/sync_canon_kernels.py \
  --catalog /path/to/viridis-canon/docs/data/catalog.json \
  --canon-commit <full-40-character-commit>
```

Review the generated diff and any binding changes before release. Canon
publication and proof status do not establish empirical accuracy, ecological
outcomes, legal compliance, market acceptance, or commercial readiness.
