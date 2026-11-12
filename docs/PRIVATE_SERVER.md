# Private single-owner server preparation

This profile targets **Ubuntu 24.04 LTS**, one trusted owner, Docker Compose 2.24.4+, Python 3.12+, and SSH key access. The OS is proposed; no host, SSH hostname, provider, region or offsite destination has been selected or provisioned. It is tested locally, not remotely deployed. It publishes only TLS on `127.0.0.1:8443`; API and PostgreSQL ports are unpublished. Access it through an SSH tunnel. No DNS, public ingress or public certificate request is needed. All application routes require the owner credential except static `/health/live`.

## Provider-independent planning and approval

Review [hosting costs and trade-offs](HOSTING_OPTIONS.md) before selecting a vendor. `deploy/server-plan.example.json` intentionally uses null/empty fields for unselected infrastructure and false approval flags. Copy it to ignored `.local/server-plan.json` without overwriting an existing plan, and fill it only after choosing real values. It contains no credentials and drives no provisioning automation. The proposed 4-GB/2-vCPU sizing is a planning allowance, not a measured production guarantee.

`deploy/server.env.example` contains only non-secret supported Compose settings. An optional copy at `.local/server.env` can be supplied as a third `--env-file`, after `.local/compose.env` and `.local/access.env`. If you change the TLS port, update the checker `--port`, SSH tunnel, SSH forwarding policy and timer templates consistently. Generate database/owner secrets on the eventual server using the existing generators; never put secret values into tracked templates. Do not put cloud API tokens in the plan.

No resource purchase, cloud API write, SSH connection, server bootstrap, offsite transfer or deployment is approved by these examples. Wait for explicit approval of provider, region, size, recurring cost and deployment plan before provisioning. The project deliberately has no auto-provision/apply command.

## Ubuntu host preparation — future operator procedure

After approval, use the [official Docker Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/) for Noble 24.04 and verify the Compose version. Establish a non-root administrator with a verified SSH key and provider recovery-console access first. Do not make SSH/firewall changes until a second key-based login works and an existing session is kept open.

`deploy/sshd-private.conf.example` is a review-only hardening proposal: key authentication, root/password login disabled, and local forwarding limited to the private proxy. It is not installed automatically. On the actual Ubuntu host, inspect existing cloud-init/drop-in settings, validate with `sshd -t`, inspect effective values with `sshd -T`, and test another connection before closing the current session. First-value precedence and existing configuration can affect the result; see the [OpenSSH reference](https://man.openbsd.org/sshd_config). Confirm owner/account choices before any installation.

In the eventual provider firewall, allow SSH only from the owner's approved source CIDRs; leave application, proxy and PostgreSQL ports closed to the internet. Review host firewall rules while preserving SSH access. Keep the Compose loopback mapping even with a firewall: [Docker-published ports can bypass UFW filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/). Verify actual published ports before relying on isolation. Enable/check the Docker service at boot, security updates and disk-space monitoring on the eventual host. None of these host changes has been performed here.

## Prepare and start

Check out a verified revision in `/opt/agenteval`, owned by the intended operator, and install dependencies with `bash scripts/install.sh`. The operator must have authorized Docker access. Generate independent database credentials and an owner token on that server; do not copy development database credentials:

```bash
python3 scripts/compose_env.py
python3 scripts/create_access_token.py
docker compose -p agenteval-private --env-file .local/compose.env --env-file .local/access.env -f compose.yaml -f compose.private.yaml -f compose.server.yaml build api proxy
docker compose -p agenteval-private --env-file .local/compose.env --env-file .local/access.env -f compose.yaml -f compose.private.yaml -f compose.server.yaml up -d --wait api worker proxy
python3 scripts/private_server_smoke.py --project agenteval-private --output artifacts/private-server-first-check.json
```

Keep `.local/compose.env`, `.local/access.env` and backup keys private and out of Git. Do not print resolved Compose configuration. The proxy is pinned by digest, runs without root or capabilities, uses a read-only filesystem and retains its private CA in a dedicated volume. The API/worker remain non-root with separate migration credentials. The profile disables the Caddy admin interface, HTTP redirects and HTTP/3, and adds a 32-KiB body bound, a 16-KB header bound and finite header/body/response/idle timeouts.

The profile intentionally permits simulated providers only. API and worker fail startup if this profile is combined with live Gemini configuration. It is not an installation-wide live quota implementation. Use the existing local Gemini profile for separately authorized experiments; do not enable live server execution until shared operation/rate budgets and cost accounting are implemented and tested. One worker lane and the existing admission/retry/deadline policies bound this private simulated preview.

## Connect privately and trust the right certificate

On the server, export only the public root certificate:

```bash
docker compose -p agenteval-private --env-file .local/compose.env --env-file .local/access.env -f compose.yaml -f compose.private.yaml -f compose.server.yaml cp proxy:/data/caddy/pki/authorities/local/root.crt .local/private-root.crt
```

Transfer that public certificate through your authenticated SSH connection, verify it came from your server, and trust it only for this private service/client context. Do not export the CA private key. For a command client, use `curl --cacert private-root.crt --user owner https://localhost:8443/health/ready`; curl prompts for the owner token password. For a browser, configure the private CA trust explicitly before logging in as `owner`. Do not bypass certificate warnings or use `--insecure`.

On your computer, run `ssh -N -L 8443:127.0.0.1:8443 YOUR_SSH_HOST`, then open `https://localhost:8443/dashboard/`. Keep the server listener on loopback. The SSH identity, host key verification, host firewall and account access are operator responsibilities; no remote server has been provisioned by these files.

## Verify and monitor

`python3 scripts/private_server_smoke.py --project agenteval-private --read-only` checks trusted TLS, authentication, dashboard access, readiness and body bounds without creating datasets or queued runs. Its default mode additionally completes four fake results and submission replay. Both modes make zero provider calls. Output files, when requested, must be new. The script does not disclose owner tokens or disable TLS verification.

Optional `deploy/systemd/agenteval-health.service` and `.timer` templates check every five minutes. Review the `/opt/agenteval` path and `User=agenteval`, then install/enable them on the server only after the manual check passes. Inspect failures with `systemctl status agenteval-health.service` and `journalctl -u agenteval-health.service`. An outbound alert destination is not configured. Docker restart policies are not a substitute for monitoring or a recovery SLA.

## Encrypted backups and restore checks

Run `.venv/bin/python scripts/backup_private_server.py --project agenteval-private`. It verifies the actual running private fake API, prevents overlapping backups, pauses API/worker writers, counts snapshot rows/schema, and takes a PostgreSQL custom dump. It encrypts the dump with authenticated Fernet encryption and a separate protected `.local/backup.key`, restarts the existing API/worker, decrypts in memory, restores into a uniquely named temporary database, compares row/schema counts and drops only that temporary database. It never restores over the application database. A restart or cleanup failure remains visible in the protected manifest; verify readiness after any failure.

This helper is for small private databases whose dumps fit in memory. It does not implement streaming large backups, continuous archiving, PITR, full content/queue recovery guarantees or host-loss recovery. The local restore check verifies counts/schema after a real restore; the earlier controlled queue restore drill is separate evidence. The generated key and encrypted backups must be recoverable independently: securely escrow the key separately and copy encrypted dumps plus manifests to an owner-controlled offsite destination. No offsite copy or remote retention policy is configured or claimed. Losing both this host and the only key copy makes the encrypted dumps unrecoverable.

The offsite transport, destination, credential profile and key escrow location stay null in the plan until selected. For either SSH storage or an object store, transfer only encrypted snapshots and manifests with independently stored recovery keys, verify the destination checksum matches the manifest, and test retrieval/decryption/restore on a separate disposable host. Set retention only after estimating retained size and confirming restore success; the helper deletes no snapshots. Provider VM images and application-aware encrypted dumps serve different recovery needs. No bucket, storage account, destination address or automatic remote-copy command has been invented or created.

Optional `deploy/systemd/agenteval-backup.service` and `.timer` templates schedule a nightly check at 03:00 UTC with up to fifteen minutes of jitter. They are not installed by the repository or local verification. Inspect and adapt the service account/path before enabling. Test one snapshot first, store its key separately, choose your offsite destination and retention policy, and restore on a separate host before relying on disaster recovery. Backups are retained without automatic deletion. Include `.local` credential recovery and proxy CA/key recovery in your secured operator plan; the database dump does not back up those files/volumes. If a proxy CA is replaced, clients need its new public root certificate.

## Update, rotate and recover

Take and verify a snapshot before a schema-changing release. Stop API/worker, build the intended revision, and bring up that revision with the same three Compose files and env files so the migrator runs before the replacement API/worker. Do not mix old and new workers. Rerun the read-only HTTPS check. Do not blindly downgrade migrations or restore over live data; first validate the selected snapshot and compatible application revision in isolation. `down` preserves operational volumes; never use `down --volumes` for the server.

For owner credential rotation, replace only the token value in the protected server file with a new strong value and recreate every API replica with the private overlay. Existing browser credentials will need updating. Database passwords, backup encryption keys, and the proxy CA require their own coordinated rotation/recovery; changing an env file does not rotate an existing PostgreSQL role. Shared owner credentials do not provide tenant isolation, independent user revocation or per-user authorization.

### Separate-host recovery rehearsal — not yet performed

After the target and recovery destination are approved, prepare a fresh disposable host and the matching application revision. Retrieve an encrypted snapshot and manifest, obtain the key through its separate escrow path, verify the ciphertext hash, and decrypt/validate the PostgreSQL custom dump without publishing plaintext or keys. Start only the fresh database/role initializer; keep API and worker stopped. Confirm the intended restore database is empty, then use `pg_restore --exit-on-error` against that fresh database. Never point it at an existing application database or add destructive cleanup flags to make conflicts disappear.

Compare restored dataset/run/job/result/document/chunk counts and migration version with the snapshot manifest, then validate role grants and the compatible application schema. Reconcile pending jobs, leases and any uncertain external calls before allowing a worker to resume. Start the private simulated stack and run the verified-TLS read-only check, followed by the fake workflow in this recovery environment. Record the observed timings and failures; do not claim an RPO/RTO from the local count/schema test. Restore the proxy CA/owner configuration securely, or provision a new private CA and explicitly update client trust. Destroy only the disposable rehearsal environment after retaining its evidence and approval to delete it.

References: [Caddy TLS](https://caddyserver.com/docs/caddyfile/directives/tls), [timeouts](https://caddyserver.com/docs/caddyfile/options), [body limits](https://caddyserver.com/docs/caddyfile/directives/request_body), [Compose overrides](https://docs.docker.com/reference/compose-file/merge/), and [Fernet](https://cryptography.io/en/latest/fernet/). Configuration and local checks are evidence for this private preview, not production certification.
