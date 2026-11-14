# Hosting recommendation for the first public deployment

**Status:** Procurement research and recommendation only. No provider has been selected or contractually reviewed; nothing has been provisioned, and there is no public URL.

## Owner decisions and constraints

- **Launch scope:** public production website for real users, not a synthetic-data demo.
- **Residency:** Pakistan-only hosting. The owner confirmed **any location within Pakistan is acceptable**; Lahore is not a strict requirement.
- **Backups:** the approved baseline remains encrypted, off-host daily backups; 30-day retention; 24-hour RPO; 4-hour RTO; quarterly restore drills. The owner confirmed that **all backup and disaster-recovery copies must also remain in Pakistan**.
- **Backup implementation:** any verified in-country off-host solution is acceptable, including provider-native backup, if it demonstrably meets the approved baseline. S3-compatible storage was an earlier preference, but is not mandatory. The current repository wrapper uses `rclone`; a non-compatible/provider-native solution would need its own reviewed, documented, monitored and restore-tested implementation before replacing that path.
- **Budget:** USD $30–$40/month planning range, excluding domain and email. The exact hard cap is unconfirmed. Compare a complete monthly bundle—not just the VM—in PKR and USD-equivalent using the actual quote/payment exchange rate. Include backups, disk, public IP, bandwidth/egress, support, taxes, and any minimum term or setup charge.

## Recommendation

Do **not** use Google Cloud Compute Engine for this requirement: Google's published Compute Engine location list includes Delhi and Mumbai but no Pakistan region, so direct GCE would not satisfy the latest in-country requirement [Google Cloud regions and zones](https://cloud.google.com/compute/docs/regions-zones).

Obtain written, like-for-like quotes for a customer-controlled Linux VM that supports the repository's Docker Compose/Caddy/PostgreSQL deployment, plus an independent in-country backup service (or compliant provider-native backup). A **4 GiB RAM VM** is an initial quote/load-test assumption, not a proven capacity target; request the provider's nearest 2–4 vCPU option, roughly 80–100 GB persistent SSD as an initial planning size, one fixed public IPv4, and clearly stated traffic limits. Validate sizing from actual synthetic load and storage growth before launch.

### Price-transparent leads to investigate first

| Service | Publicly advertised information checked 9 Nov 2026 | What remains unverified; not an endorsement |
|---|---|---|
| **CloudVPS.pk Lahore VPS — VM lead** | Its page lists a 4 GB plan at **PKR 7,000/month** with 4 CPU cores, 100 GB NVMe, 1 TB bandwidth and one dedicated IPv4, and advertises root access and Lahore location [Lahore VPS plans](https://cloudvps.pk/lahore-vps). | Ask for a written quote and contract naming the actual facility and confirming the VM and customer data stay in Pakistan; verify Docker Engine/Compose/root access, CPU guarantees, backup options, SLA, taxes, renewal/term, support, export/deletion, and support/telemetry handling. The public page alone is not residency evidence or a production assurance. Confirm order availability with sales before relying on the listing. |
| **QCloud Object Storage — off-host backup lead** | QCloud advertises an S3-compatible object API, Standard storage from **PKR 6/GB-month**, and storage in its Karachi and Islamabad facilities [QCloud Object Storage](https://qcloud.pk/object-storage-service/). | Request written confirmation of in-country storage and replication/DR, all fees and minimums, retrieval/egress/API costs, account separation, retention/deletion semantics, encryption and key controls, and support access. Test the repository's restricted `rclone` workflow with a dedicated synthetic-data prefix before any production use. Public claims and rates are not a signed quote or a verified restore. |
| **Nayatel S3 Object Storage — backup alternative** | Nayatel advertises S3-compatible storage hosted in Pakistan and lists **PKR 15/GB-month** [Nayatel S3 storage](https://nayatel.com/cloud/storage/s3-object-storage). | Confirm exact facility/replication, taxes and whether the public rate covers the required storage class; ask about API/egress/retrieval, retention controls, key/access controls and contract terms. A public rate is not a full quote or a verified restore. |

A useful storage-cost formula for comparing object-storage quotes is `monthly storage charge = total retained GB × quoted PKR/GB-month`, plus requests, retrieval/egress, taxes, minimums, and any account fees. Because the backup wrapper stores daily encrypted sets, the 30-day footprint depends on real database/photo volume; the production corpus is empty and no representative backup size has been measured. Do not present the VM's PKR 7,000 list price as an all-in $30–$40 quote.

### Quote-only / likely higher-cost local-cloud options

- **PTCL Smart Cloud:** PTCL advertises in-country IaaS plus Backup-as-a-Service and disaster recovery, and describes geographically redundant local facilities [PTCL Cloud Services](https://ptcl.com.pk/home/pagedetail?itemid=424&linkid=1004). An official pricing page still surfaced an older listing of $50/month for a 2 GB VM and $95/month for 4 GB; treat that page as potentially stale, not a current quote [PTCL pricing listing](https://ptcl.com.pk/Home/PageDetail?ItemId=436). Ask whether a small-business configuration exists within the planning range and whether backup/DR copies can be contractually restricted to Pakistan.
- **TMC Cloud:** advertises IaaS, BaaS and DRaaS from a Tier III facility in Lahore with business support [TMC Cloud](https://www.services.tmcltd.com/cloud-hosting-pakistan/). Pricing is quote-only in the material reviewed; confirm the VM is available as an unmanaged, Docker-capable Linux host and ask whether the commercial minimum fits the planning range.
- **Wateen Cloud:** local provider offering compute/storage services; request an itemized VM and backup quote and written facility, replication, support and data-processing terms [Wateen Cloud](https://wateen.com/wateen-cloud/). No usable public price was found.

The local-VM list price may be attractive, while the enterprise providers may offer more managed operations. Neither price nor marketing language alone resolves security, availability, support, privacy, or disaster-recovery suitability. Compare evidence and contract terms first. If no responsible, in-country option fits the planning range, ask the owner to revisit the budget rather than remove backup, security, or residency requirements.

## Mandatory provider due diligence

1. **Residency in writing:** identify the city/facility for the VM, persistent disks, database, private user-uploaded photos, logs and service metadata, snapshots, backups, replicas and disaster-recovery copies. Confirm no cross-border replication or out-of-country storage. Ask where support/telemetry is processed and what support access entails.
2. **Deployment compatibility:** confirm customer-controlled Linux/root or sudo, Docker Engine and Compose, persistent storage, one fixed public IPv4, inbound TCP 80/443, and that database/API ports can remain private. Confirm resource guarantees and no prohibited container/runtime terms.
3. **Full recurring price:** itemize VM, disk, IPv4, bandwidth/egress, snapshots, backup storage, restore/retrieval, support, monitoring, taxes, minimum commitment, setup fee, and overages. State PKR total and a USD-equivalent using the quote date's exchange rate/payment fees.
4. **Backup/recovery:** confirm a genuinely off-host failure domain, daily encrypted copies, 30-day retention, no automatic cross-border replicas, tested export, restore access, and a path to satisfy 24-hour RPO, 4-hour RTO and quarterly drills. Provider-native snapshots alone do not establish application-consistent PostgreSQL/photo backup or the approved objectives.
5. **Security and exit:** request SLA and incident-response terms; access and audit controls; encryption/key ownership; deletion, retention, portability and account-termination process; data-processing terms; backup deletion behavior; and notice obligations for incidents.

## Procurement sequence and launch gates

1. Send the same requirements to CloudVPS, PTCL, TMC and Wateen; request a full quote and written residency/technical answers. Compare QCloud and Nayatel for backup separately. A copy-ready inquiry and scorecard are in [`HOSTING_VENDOR_RFQ.md`](HOSTING_VENDOR_RFQ.md).
2. Reject any quote that cannot document Pakistan-only primary data **and** Pakistan-only backup/DR copies, or that cannot support this Docker deployment and restore path.
3. Select a host and backup method only after the owner approves the complete price and terms. Do not send credentials or private data in ordinary email/chat; use provider account onboarding and an approved secure channel.
4. Provision only an isolated staging environment with synthetic data first. Test load/sizing, deployment, monitoring, backup completion alerts, a timed restore, and provider exit/export. Do not migrate real user data until the existing data-rights/reviewer, privacy/legal, hosted CI/image scan, PostgreSQL, backup, security and operations gates in [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md) are closed.

**No host, backup provider, quote, contract, project, domain, DNS, or public endpoint has been selected or provisioned. Production readiness remains open.**
