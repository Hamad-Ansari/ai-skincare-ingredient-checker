# Hosting and backup vendor quote request

**Purpose:** collect comparable quotes for a public production web application. This is an inquiry template, not an authorization to provision or send any customer data. Do not include credentials, private keys, real user records, sample photos, or unreleased security details in ordinary email.

## Copy-ready inquiry

**Subject:** Quote request — Pakistan-hosted Linux VM and in-country backup

Hello,

Please provide an itemized written quotation for a small production web application. Pakistan-only data location is required: the application host, database, uploaded images, service logs/metadata, backups, replicas, and disaster-recovery copies must remain within Pakistan. Any city within Pakistan is acceptable. Please state the exact facility/city and confirm the location and no-cross-border-replication requirement in the service terms or contract.

### Compute / VM

Please quote your nearest suitable monthly configuration around:

- Linux VM with 4 GiB RAM and approximately 2–4 vCPU (please state guaranteed/dedicated vs shared resources and any CPU limits).
- Approximately 80–100 GB persistent SSD as an initial planning size; please state filesystem/block storage details, expansion price, and snapshot behavior.
- Customer-controlled root/sudo access and permission to run Docker Engine plus Docker Compose.
- One fixed public IPv4; inbound TCP 80/443 permitted. The PostgreSQL and application/API ports will remain private and are not to be exposed publicly.
- Included monthly traffic/egress, overage rates, network/uplink limits, DDoS/firewall options, and any public-IP charges.

These sizes are planning assumptions and may be adjusted after staging tests. Please also quote the smallest practical option if it is materially less expensive, while stating any trade-offs.

### Backup / recovery

Please quote a separate, genuinely off-host backup option or provider-managed service that can meet all of the following, with all copies and replication remaining in Pakistan:

- Encrypted daily backups covering PostgreSQL and the private uploaded-image volume.
- 30-day retention; a 24-hour recovery point objective; 4-hour recovery time objective.
- Quarterly restore drills and export/restore access for the customer.
- Independent backup access controls and protection against accidental deletion/compromised VM credentials.
- A documented process to verify backup completion, retention, restore integrity, restore time, and deletion at account termination.

The application can use an S3-compatible API with `rclone`, but this is not mandatory: a provider-native backup service is acceptable if it demonstrably meets the same residency, encryption, scope, access-control, retention, monitoring and restore requirements. Please specify which approach you are quoting, what is included, and all limitations. A VM snapshot by itself is not assumed to be application-consistent or sufficient.

### Residency, security, terms and pricing

Please answer each item explicitly:

1. Exact city/facility for compute, block storage, object/backup storage, snapshots, replicas and disaster recovery. Do any provider, subcontractor, control-plane, support or telemetry operations store or access customer data outside Pakistan? Is cross-border replication disabled and contractually prohibited?
2. Which employees/contractors can access the VM, backup data, keys or logs; how is access authorized, logged, and revoked? What encryption at rest/in transit is included, and can the customer manage the backup encryption key?
3. How are PostgreSQL and uploaded-image data made consistent for backup and restored together? Can a restore be performed to a customer-controlled isolated environment? What are the tested maximum RPO/RTO and restore/egress charges?
4. What are the uptime/SLA, support hours, severity response targets, incident/breach notification process, maintenance windows, and planned downtime policy?
5. What are the data retention/deletion, portability/export, account-cancellation and backup expiry terms? Can all customer data and all retained copies be deleted on request or termination, and what evidence is provided?
6. Provide separate recurring charges for compute, disk, IP, traffic/egress, backup storage/service, restore/retrieval, support, monitoring and taxes; one-time/setup fees; minimum contract term; price validity; and overage rates. Quote totals in PKR/month. If quoted in another currency, state the exchange/settlement method and fees.
7. Please confirm Docker Engine/Compose and the proposed Linux distribution/version are supported and permitted under your acceptable-use terms, and identify any root, firewall, port, CPU or storage restrictions.

Please do not provision anything or request credentials at this stage. A written quote and product/contract documentation are sufficient for initial evaluation.

Thank you.

## Evaluation scorecard

A response is **not eligible** if the vendor cannot confirm Pakistan location for both primary data and all backup/DR copies, or cannot provide a Docker-capable Linux deployment and an acceptable restore/export path.

| Criterion | Required evidence | Vendor response / status |
|---|---|---|
| Primary data residency | Written city/facility for VM, disks, database, photos and logs/metadata | |
| Backup/DR residency | Written location for every copy, replica, snapshot and DR copy; no cross-border replication | |
| VM compatibility | Linux/root or sudo, Docker/Compose, private persistent volumes, fixed public IPv4, ports 80/443 | |
| Capacity | RAM, CPU share/guarantees, disk, traffic, expansion limits and availability | |
| Backup scope | PostgreSQL plus image volume; encryption before or at source; daily job | |
| Retention and objectives | 30-day retention; 24-hour RPO; 4-hour RTO; quarterly restore drills | |
| Isolation and deletion safety | Separate access/credentials/failure domain; versioning or deletion protection; dedicated scope | |
| Restore and exit | Timed isolated restore, export, egress/retrieval fees, account-end deletion proof | |
| Security/operations | SLA, support response, audit/access controls, incident notification, key ownership | |
| Full cost | PKR total/month including tax, IP, bandwidth, backup, support and overages; setup/term/renewal | |
| Owner approval | Complete quote/terms accepted; planning range or owner-approved updated cap | |

## Quote comparison worksheet

| Vendor/service | Role | Compute or storage configuration | Advertised / quoted price | Residency evidence | Backup + restore evidence | Total monthly PKR | USD-equivalent / date | Decision |
|---|---|---|---|---|---|---:|---|---|
| CloudVPS.pk | Candidate VM | Lahore 4 GB listing; confirm Docker and terms | Public list: PKR 7,000/month; not a quote | Pending | Pending | | | |
| PTCL Smart Cloud | Candidate IaaS / BaaS / DRaaS | Obtain current small-business quote | No current quote; older listed price may be stale | Pending | Pending | | | |
| TMC Cloud | Candidate IaaS / BaaS / DRaaS | Obtain quote and minimum term | Quote required | Pending | Pending | | | |
| Wateen Cloud | Candidate IaaS / storage | Obtain quote and minimum term | Quote required | Pending | Pending | | | |
| QCloud OSS | Candidate object backup | S3-compatible; price by retained GB | Advertised Standard from PKR 6/GB-month; confirm all fees | Pending contractual confirmation | Pending compatibility/restore test | | | |
| Nayatel S3 | Candidate object backup | S3-compatible; quote by retained GB | Public listing: PKR 15/GB-month; confirm all fees | Pending contractual confirmation | Pending compatibility/restore test | | | |

Record only public links, quote references and non-secret answers here. Keep signed contracts, account identifiers, IP addresses, credentials, encryption identities, and private user data in their approved restricted locations—not in this repository or a public report.
