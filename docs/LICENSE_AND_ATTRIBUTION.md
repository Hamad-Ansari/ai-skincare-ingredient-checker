# License and attribution status

## Source-code reuse decision: no public license

**Owner decision (date not independently recorded):** the project will have **no public source-code license or reuse grant**. No `LICENSE` file is added. Treat the repository code as copyrighted and do not copy, modify, redistribute, or use it outside the owner's authorized project without separate written permission. Do not describe the project as open source or MIT-/Apache-licensed.

This is an operational record of the owner's choice, not legal advice and not a substitute for confirming ownership and contributor rights. Revisit the decision with qualified counsel before publishing source, accepting outside contributions, or distributing software to others. A private deployment by the owner does not grant third parties rights to the source.

## Data, evidence, images, fonts, and models are separate

The no-public-code-license decision does **not** establish rights to third-party product data, cosmetic evidence, excerpts, labels/photos, fonts, images, or model weights. Review and record each source's current terms, attribution text, allowed uses, modification/reproduction limits, expiry/review date, and evidence of permission before ingesting or redistributing any material. Source-specific rights must continue to be enforced by the catalog/evidence workflow.

No production ingredient/rule/evidence corpus or third-party product-photo set is shipped by this repository. Test fixtures are synthetic unless a fixture explicitly records otherwise; do not add copyrighted evaluation labels or images without documented rights.

## Software dependency notices

Python runtime and development dependencies are pinned in `backend/requirements*.txt`; the browser-test dependencies are locked in `frontend/package-lock.json`; the Dockerfile uses the Python 3.11 slim base image, and Compose uses PostgreSQL, Caddy, and BusyBox images. Review each dependency/image's license and security notices for the exact version/digest actually deployed. Before distributing binaries or containers to others, generate and review a complete release-specific SBOM/notice bundle. The absence of a repository `LICENSE` is not a grant for dependency or container redistribution.

The Compose image tags are documented in `docs/DEPLOYMENT.md`; they are not all digest-pinned yet.

## Pre-release checklist

- [x] Owner selected no public source-code license or reuse grant; no `LICENSE` file is added. Do not redistribute without separate permission.
- [ ] Copyright ownership and contributor permissions are confirmed before any external distribution or contribution.
- [ ] Build a release-specific SBOM/notices bundle for Python/npm packages and container images; review notice/reciprocal-license obligations before distributing artifacts.
- [ ] Every non-synthetic evidence, ingredient, evaluation, photo, font, model, and other data asset has documented origin, license/permission, attribution, allowed purpose, and review date.
- [ ] Public claims do not imply that a code or dataset license is a safety, clinical, or regulatory endorsement.
