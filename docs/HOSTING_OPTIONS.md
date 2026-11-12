# Private AgentEval hosting options

Planning date: **November 11, 2026 (America/Chicago)**. No provider is selected, no account/resource was created, and no live deployment was attempted. Ubuntu 24.04 LTS is the proposed host OS. Prices below are published list-price estimates, not quotes; confirm region, current availability and tax at checkout only after approval. No promotional credits are assumed.

## What you would be paying for

A VPS is a rented Linux computer. On either option below, the same Docker Compose files run the API, one worker, PostgreSQL and the private TLS proxy. PostgreSQL uses the server's local disk through a named Docker volume; this adds no separate managed-database subscription. That volume survives container restarts, but losing/deleting the VM can still lose its data. You maintain Ubuntu, Docker, database updates and backups yourself.

The durable queue and Docker restart policies help the worker recover after ordinary process failures. They do not make a single VM highly available. If the machine fails, both API and worker stop until recovery. Neither provider has been benchmarked with AgentEval, so this comparison makes no claim that one runs workers more reliably. More CPU/RAM is not a fix for the historical lock-timeout cause.

For planning, 4 GB RAM / 2 shared vCPUs / about 80 GB disk gives more room for local image builds and the combined database/application stack. This is an engineering allowance, not measured capacity. A 2-GB pilot costs less but should be measured carefully; build images elsewhere if server builds cause memory pressure. This project calls external models, so it does not need a GPU server.

## Two verified low-cost VM options

All estimates are **USD/month**, excluding tax, overage, offsite storage and Gemini usage. Totals include the stated optional provider backup product; you may choose not to purchase it, but independent encrypted database backups are still needed.

| Option | 2-GB pilot | 4-GB planning size | Provider backup option | Estimated VM + provider backups |
|---|---:|---:|---|---:|
| DigitalOcean Basic, regular CPU | $12; 1 vCPU, 50-GiB SSD | $24; 2 vCPUs, 80-GiB SSD | Weekly adds 20%; daily adds 30% | 2 GB: **$14.40 weekly / $15.60 daily**. 4 GB: **$28.80 weekly / $31.20 daily** |
| Akamai Cloud / Linode Shared CPU | $12; 1 vCPU, 50-GB disk | $24; 2 vCPUs, 80-GB disk | $2.50 for 2 GB or $5 for 4 GB; daily, weekly, biweekly and manual slots | 2 GB: **$14.50**. 4 GB: **$29.00** |

Compute sources: [DigitalOcean plans](https://www.digitalocean.com/pricing/droplets), [Akamai Shared CPU plans](https://www.akamai.com/cloud/pricing/cpu). Backup sources: [DigitalOcean percentages](https://docs.digitalocean.com/products/backups/details/pricing/), [Akamai backup prices](https://www.akamai.com/cloud/pricing/backups), [Akamai backup retention/slots](https://techdocs.akamai.com/cloud-computing/docs/getting-started-with-the-linode-backup-service).

DigitalOcean offers a straightforward choice between cheaper weekly and more expensive daily image backups. Linode's comparable small VM has a similarly priced add-on that includes a daily slot plus longer-spaced copies. Those backups stay within the hosting provider's system; neither replaces the application's encrypted PostgreSQL dump or proves database-consistent disaster recovery.

On both, the application keeps the same named PostgreSQL volume and one durable worker. Changing provider means moving a verified dump and configuring the same Compose deployment, not rewriting the application. The main trade-off is your monthly backup preference and available region, rather than a demonstrated worker-performance difference. A managed database would reduce some administration work but adds a separate bill and would require verifying pgvector, privileges and migrations; it is outside these estimates.

## Independent offsite backups

Keep the existing encrypted snapshots and manifests outside the VM, and escrow the encryption key separately. A second trusted machine using SSH or an approved object-storage bucket are provider-independent destinations. Both remain unselected in `deploy/server-plan.example.json`. No transfer command has been executed.

For a storage-only price illustration, [Backblaze B2](https://www.backblaze.com/cloud-storage/pricing) lists $6.95 per TB per 30-day month: 100 GB of retained data is approximately **$0.70/month for storage before allowances**. Restore/download, transaction, network and tax rules must be checked for the chosen destination and workload. This is a possible independent backup destination, not a selected vendor, guaranteed free tier or all-in bill. Actual retained size is unknown; database snapshots, keys, retention and separate-host restores need approval/configuration.

## Conditional recommendation, after those trade-offs

For this project's first private server, I would tentatively choose **Linode Shared 4 GB plus its backup add-on, about $29/month before extras**, if daily provider backups are important: its published backup schedule is more frequent than DigitalOcean's almost-equally-priced weekly option. DigitalOcean 4 GB is equally reasonable if you prefer its interface or region; daily backup pricing brings that baseline to $31.20. A 2-GB Linode pilot at about $14.50 including provider backups is the lower-cost experiment, with sizing/build constraints to validate first.

This is a planning judgment from the published prices and the application's architecture, not a provider reliability test. No purchase or provisioning is authorized by this recommendation. The next decision is your provider/region/size and monthly budget, followed by an explicit approval before any paid resource is created. Offsite destination and key recovery must also be chosen before relying on backups.
