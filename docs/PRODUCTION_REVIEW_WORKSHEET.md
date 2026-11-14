# Production source, reviewer, and evaluation worksheet

**Status:** Blank intake/review aid only. It records no approval and is not a legal, medical, or safety sign-off. Complete one source worksheet per distinct source/package and one approval record per reviewed import/rule version.

## Handling and privacy

- Keep rights documents, licensed data, reviewer correspondence, and any non-public source material in an owner-approved restricted location—not in a public issue, public report, or tracked source file.
- `data/private/` is Git-ignored for private source packets; verify the ignore rule before placing anything there and keep a separately access-controlled original/checksum. Do not place real user scans, private photos, account data, credentials, tokens, or encryption keys in a source packet.
- Only provide reviewer qualification details needed to establish relevant scope. Do not collect or circulate personal addresses, identity documents, license numbers, or unrelated CV details unless a separately approved process requires them.
- Do not paste a confidential source dataset into chat. Share a redacted evidence summary or non-sensitive manifest first; transfer underlying material only through the approved private channel.
- Never treat a public URL, an “open data” label, a citation, or an internal reviewer checkbox as proof of reuse permission or safety.

## A. Source package record

Create a separate copy of this section for each package. Use a stable, non-personal source ID.

### Identity and provenance

- Source/package ID:
- Publisher / author / responsible organization:
- Title / dataset / document name:
- Canonical URL or restricted delivery reference:
- Version, release, or document revision:
- Retrieved / received date and timezone:
- File format, language(s), and record count (if known):
- SHA-256 checksum(s) of received originals:
- Source owner / contact route (restricted record; do not include private contact details in public reports):
- Known derivatives, upstream sources, or collection method:
- Known gaps, exclusions, corrections, or version changes:

### Rights and permitted-use review

Attach or privately reference the exact license, contract, permission, terms-of-service snapshot, or written authorization. Record the relevant clause/page and date; do not paraphrase away restrictions.

| Use or condition | Allowed? (yes / no / limited / unclear) | Exact evidence / limit / reviewer note |
|---|---|---|
| Access, download, and store the source in the service | | |
| Normalize, transform, or create derived ingredient records | | |
| Use for a commercial/public production service | | |
| Display names, facts, classifications, or source-linked summaries to users | | |
| Display direct excerpts/quotes (maximum length or other restriction) | | |
| Include the source in an evaluation set or benchmark | | |
| Redistribute the original data or derived records | | |
| Store in the selected Pakistan-only deployment and backup locations | | |
| Retain after license expiry, withdrawal, account closure, or deletion request | | |
| Other restrictions, territory, attribution, notices, or use conditions | | |

- Rights holder / granting authority verified? Evidence:
- Territory, term, effective date, expiry/review date:
- Required attribution/citation text and placement:
- Excerpt / transformation limits:
- Data deletion or source-withdrawal obligations:
- Legal/privacy reviewer and review reference:
- Rights disposition: **pending / approved for stated uses / restricted / rejected**
- Approved uses and excluded uses (be specific):

**Gate:** Any unclear permission is **pending**, not approved. Stop before import or user display until permission for each intended use is established. Legal approval of source terms is separate from domain review of scientific/technical meaning.

## B. Mapping and import review

- Import manifest path/reference (restricted location):
- Manifest version and SHA-256:
- Parser/importer version:
- Target catalog schema / normalization version:
- Import batch ID (after submission):
- Source fields mapped to application fields:
- Unit, locale, language, and missing-value interpretation:
- Canonical ingredient identifiers and alias strategy:
- Duplicate, conflict, ambiguity, and rejected-row handling:
- Provenance field retained for every imported row:
- Data minimization and retention check:

| Row / record key (non-personal) | Proposed canonical mapping | Evidence/source record | Reviewer decision (approve / reject / needs clarification) | Reason / correction | Version |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

Do not copy restricted source contents into this tracked worksheet. Keep row-level review in the approved private system; publish only redacted totals and non-sensitive rationale.

## C. Qualified reviewer scope and approval

Complete in a restricted record. A reviewer being “confirmed” is not the same as documenting their relevant qualifications, scope, review, or written approval.

- Reviewer reference/initials (use a private identity record where necessary):
- Relevant role and qualification type / discipline:
- Jurisdiction or specialty, if applicable:
- Relevant experience for the exact review scope:
- How qualifications and current standing were checked (restricted reference):
- Conflicts of interest, funding, source relationships, or limitations disclosed:
- Date/version/materials reviewed; source/import/rule manifest checksum:
- Review methods: (for example, record-level sample or full review; explain why adequate)
- Items in scope: identity/normalization, source meaning, evidence mapping, rule conditions, severity, user-facing wording, citations, evaluation protocol:
- Items explicitly out of scope:
- Decisions and rationale, including unresolved disagreements:
- Conditions, expiry/re-review trigger, and required follow-up:
- Written approval reference and secure storage location:

### Review decisions

| Review item | Decision (approve / revise / reject / not reviewed) | Evidence/version reviewed | Limitations, changes, or rationale |
|---|---|---|---|
| Source interpretation and record mapping | | | |
| Canonical names and ambiguous aliases | | | |
| Each evidence mapping and citation | | | |
| Each deterministic rule and its triggering conditions | | | |
| Finding severity and user-facing explanation | | | |
| Safety disclaimers and no-finding language | | | |
| Evaluation cases, labels, and adjudication protocol | | | |

Reviewer statement (complete only after the review; do not pre-check):

> I reviewed the identified materials and exact versions within the scope recorded above. My approval applies only to those materials and conditions, and does not establish legal permission, clinical effectiveness, universal product safety, or coverage beyond the stated scope. Unresolved issues and limitations are recorded above.

- Reviewer signature / approval reference:
- Date:
- Owner acceptance of scope and limitations:
- Separate legal/privacy sign-off reference:
- Technical import verification reference:

## D. Evaluation plan (if a test/evaluation corpus is supplied)

- Evaluation ID and restricted location:
- Rights evidence explicitly covering evaluation use:
- Dataset source, version, checksum, sample count, and intended population/coverage:
- Privacy screening / de-identification review; excluded personal or sensitive material:
- Annotation instructions and version:
- Ground-truth label definitions, ambiguity labels, and allowed abstentions:
- Annotator qualifications and blinding/separation from development examples:
- Adjudication process, disagreement resolution, and inter-rater reporting:
- Train/development/evaluation separation; leakage controls:
- Metrics, denominators, confidence/uncertainty reporting:
- Predeclared acceptance thresholds and who approved them:
- Failure analysis plan and remediation triggers:
- Report disclosure limits and permitted audience:

For an ingredient-label evaluation, consider character/word recognition error, ingredient extraction precision and recall, exact-name resolution accuracy, unresolved/ambiguous rate, per-rule false-positive/false-negative counts, citation support/validity, and failure cases. Define every denominator and threshold before examining results. These measurements do not establish clinical performance or individual safety.

## E. Activation gates and decision log

Do not activate production records or findings until every applicable gate is closed with evidence.

| Gate | Required evidence | Status (open / pass / fail / N/A) | Evidence reference, version, owner, date |
|---|---|---|---|
| Source provenance/version/checksum complete | | open | |
| Rights cover storage, transformations, intended commercial/user display, attribution, and retention | | open | |
| Pakistan-only data and backup handling reviewed where applicable | | open | |
| Data dictionary, mapping, normalization, and ambiguity behavior reviewed | | open | |
| Row-level import review complete; rejected/unresolved rows excluded | | open | |
| Qualified reviewer scope and qualifications documented | | open | |
| Evidence mappings and citations approved for the exact version | | open | |
| Every rule and user-facing claim reviewed and versioned | | open | |
| Evaluation protocol/thresholds approved before measurement | | open | |
| Evaluation results, uncertainty, and limitations reviewed | | open | |
| Privacy/legal and data-retention obligations signed off | | open | |
| Owner explicitly authorizes staged activation | | open | |

### Decision log

| Date | Version / checksum | Decision | Decision owner / reviewer | Conditions, limits, and next review date |
|---|---|---|---|---|
| | | | | |
| | | | | |

## Current project evidence status

The owner reports that a source packet is ready and a qualified reviewer is confirmed. At the latest workspace check, no source packet or reviewer evidence was present under `data/private/`; `data/seed/ingredient_seed_manifest.json` still contains no sources or imports. Therefore no source rights, row mappings, qualifications, reviewer scope, written approval, or real-data evaluation have been reviewed here. Keep all activation gates open and the production seed empty until the evidence is supplied and assessed.
