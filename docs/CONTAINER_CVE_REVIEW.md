# Container CVE review — remote image snapshot

**Disposition:** Partial, provisional evidence only. This was a Dockerless scan of the current remote tags, not the hosted CI run and not a scan of the final built API image. The CI severity gate remains unverified.

## Method and limits

- Scanned with Trivy CLI **0.70.0** from the official release; the downloaded Linux archive was checked against its published SHA-256 checksum before execution.
- Used remote registry image sources, the vulnerability scanner, all severity levels, JSON output, and the default behavior that includes unfixed findings. No threshold was applied to this snapshot.
- Tags were resolved to the immutable digests listed below on the Linux/x86-64 runner. Tags are mutable; these digests identify the exact image snapshots scanned.
- The JSON `CreatedAt` fields record 2026-11-13T09:09:17Z–09:09:42Z, later than the canonical session date (2026-11-09, Asia/Karachi). A Docker Hub metadata cross-check also showed `postgres:17-alpine` updated on 2026-11-12 and `caddy:2-alpine` on 2026-11-13, while `python:3.11-slim` was updated on 2026-11-08. Thus the PostgreSQL/Caddy tags in these reports postdate the canonical review date. Treat this as a sandbox clock/registry-date discrepancy: the snapshot is useful for provisional triage, but not time-valid release evidence until rerun under a trusted hosted runner. The Trivy JSON does not record the vulnerability-database revision.
- `python:3.11-slim` is the Dockerfile base only. It is **not** the fully built application image. The CI job must scan that image after build; the Python lock-file `pip-audit` is separate evidence.
- Counts below are Trivy finding records, not necessarily unique CVE identifiers across all packages. No reachability/exploitability review or exception suppression was performed.

## Results

| Remote image tag | Immutable digest recorded by Trivy | Findings by severity | Fixable HIGH/CRITICAL findings (owner-selected CI gate) |
|---|---|---:|---:|
| `postgres:17-alpine` | `sha256:d3244e8ce3f165ee3c93d9c4a4b1d0fe48b3a89e2287b717fdcbbde92d405065` | 62 total: 1 CRITICAL, 25 HIGH, 31 MEDIUM, 3 LOW, 2 UNKNOWN | **26** |
| `caddy:2-alpine` | `sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0` | 8 total: 2 HIGH, 4 MEDIUM, 2 UNKNOWN | **1** |
| `busybox:1.37.0` | `sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec` | 0 | **0** |
| `python:3.11-slim` (Dockerfile base) | `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535` | 218 total: 51 HIGH, 96 MEDIUM, 67 LOW, 4 UNKNOWN | **4** |

The PostgreSQL image's fixable HIGH/CRITICAL records were attributed by Trivy to Go `stdlib` v1.24.6; this pass did not determine which embedded binary or whether a particular finding is reachable. Caddy had a fixable HIGH report for `golang.org/x/net` v0.60.0 (Trivy listed v0.62.0 as fixed). The Python base reports included fixable HIGH findings for `jaraco.context`, `wheel`, and Debian `zlib1g` packages.

**Policy implication:** If the CI scan resolves the same image digests, the configured fixable HIGH/CRITICAL threshold will block on the PostgreSQL and Caddy images, and likely the built API image due to its Python base. BusyBox showed no vulnerability findings in this snapshot. Do not use these results to approve the current images; update/review the images and rerun.

## Raw reports

- [`reports/container-cve/postgres-17-alpine.json`](../reports/container-cve/postgres-17-alpine.json)
- [`reports/container-cve/caddy-2-alpine.json`](../reports/container-cve/caddy-2-alpine.json)
- [`reports/container-cve/busybox-1.37.0.json`](../reports/container-cve/busybox-1.37.0.json)
- [`reports/container-cve/python-3.11-slim.json`](../reports/container-cve/python-3.11-slim.json)

## Next remediation work

1. Review the full findings against upstream release notes/advisories; do not add blanket ignores.
2. Select updated, patched image versions/digests, rebuild the API image, and rerun both the full report and the blocking policy against the exact release images.
3. Record any justified exception with owner, evidence, expiry, and compensating control; establish an image update/refresh cadence.
