# Hosting

How to run the app in a container locally and deploy it to Azure. The
scaffolding-sdlc skill copies the stack's `Dockerfile`, `.dockerignore`, and
`docker-compose.yml` to the repo root, the Bicep under `infra/`, and a single
`cd.yml` into `.github/workflows/`.

You choose **one** hosting model at scaffold time, and the matching `infra/main.bicep`
+ `cd.yml` are installed:

- **App Service (container)** — turnkey web conveniences (Easy Auth, managed certs,
  deployment slots); always-on. Recommended for a single public web app. *(below)*
- **Azure Container Apps (ACA)** — scale-to-zero economics, automatic HTTP autoscaling,
  native revisions/traffic-splitting; cold starts when scaled to zero. *(further below)*

Both share the `Dockerfile`/`docker-compose.yml`, the ACR + Postgres Bicep, and the
Azure OIDC secrets.

## Run locally with Docker

```bash
docker compose up --build
# App: http://localhost:8000   (Postgres runs as the `db` service)
```

`docker-compose.yml` sets `DATABASE_URL` to the Postgres service, so the
container exercises the same database engine as production. Without
`DATABASE_URL` the app falls back to SQLite (plain `python manage.py runserver`).

- **Python (API)** — the image runs `migrate` then `gunicorn`.
- **Fullstack** — a multi-stage build compiles the React SPA, and Django serves
  it (WhiteNoise for assets, an index.html fallback for client-side routes) at
  `/` with the API under `/api`.

## Deploy to Azure (App Service + ACR + Postgres)

### 1. Provision infrastructure (Bicep)

```bash
az group create -n <rg> -l eastus
az deployment group create \
  -g <rg> \
  -f infra/main.bicep \
  -p infra/parameters/prod.parameters.json \
  -p pgAdminPassword='<choose-a-strong-secret>'
```

This creates an Azure Container Registry, a PostgreSQL Flexible Server (+ `app`
database), and a Linux container App Service. The Web App uses a system-assigned
managed identity with **AcrPull** to pull images — no registry credentials are
stored. `DATABASE_URL` is injected as an app setting automatically.

Edit `infra/parameters/<env>.parameters.json` (`appName`, `imageName`,
`appServiceSku`) per environment. `pgAdminPassword` is `@secure()` — pass it at
deploy time, never commit it.

### 2. Wire up CD (`cd.yml`)

The workflow builds the image in ACR and points the Web App at it on every push
to `main`. Configure once:

- **OIDC federated credentials** for a Microsoft Entra app/service principal
  with access to the resource group, then add repo **secrets**:
  `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- Repo **variables**: `AZURE_RESOURCE_GROUP`, `AZURE_ACR_NAME`,
  `AZURE_WEBAPP_NAME`.

The deploy job is gated on `AZURE_WEBAPP_NAME` — until you set it, the workflow
no-ops, so it's safe to merge before Azure is set up.

## Deploy to Azure Container Apps (ACA + ACR + Postgres)

The ACA variant runs the same container image on a serverless platform with
scale-to-zero and a dedicated migration Job. Migrations do **not** run in the
container entrypoint here (`RUN_MIGRATIONS_ON_START=false`) — a separate Job owns
them, because multiple replicas would otherwise race.

### 1. Provision infrastructure (Bicep)

```bash
az group create -n <rg> -l eastus
az deployment group create \
  -g <rg> \
  -f infra/main.aca.bicep \
  -p infra/parameters/aca.prod.parameters.json \
  -p pgAdminPassword='<choose-a-strong-secret>'
```

This creates an ACR, a PostgreSQL Flexible Server, a Container Apps managed
environment (+ Log Analytics), the Container App, and a manual-trigger **migration
Job**. The app and Job each use a system-assigned identity with **AcrPull**.

Edit `infra/parameters/aca.<env>.parameters.json` per environment:

- `minReplicas` — **defaults to `1` (always-warm)**. Set to `0` for scale-to-zero
  (idle ≈ $0, at the cost of a cold start on the first request after idle).
- `maxReplicas`, `cpu`, `memory` — scale/size per environment.

### 2. Wire up CD (`cd.yml`)

On every push to `main` the workflow: builds the image in ACR → points the
migration Job at the new image, **runs it, and waits** (a failed migration stops
the deploy — traffic is never routed to a new image against an un-migrated schema)
→ updates the Container App to the new revision.

- Repo **secrets**: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- Repo **variables**: `AZURE_RESOURCE_GROUP`, `AZURE_ACR_NAME`,
  `AZURE_CONTAINERAPP_NAME`, `AZURE_CONTAINERAPP_JOB`.

Gated on `AZURE_CONTAINERAPP_NAME` — no-op until set.

### 3. Run migrations / one-off commands manually

The migration Job is provisioned once and invocable any time. The default command
is `migrate --noinput`; override it to run any management command:

```bash
# default migration
az containerapp job start -g <rg> -n <job-name>

# one-off command (createsuperuser, loaddata, a contract migration, etc.)
az containerapp job start -g <rg> -n <job-name> \
  --command "/bin/sh" --args "-c","python manage.py createsuperuser --noinput"
```

Use this for: a migration that failed mid-deploy, long data backfills kept out of
the deploy path, expand/contract (drop-column) migrations run after the new code is
healthy, rollbacks, and DB-restore catch-up.

### 4. Ephemeral preview environments (`automation-deploy-test` label)

Add the **`automation-deploy-test`** label to a PR and `cd-preview.yml` deploys a
throwaway `…-pr-<n>` Container App (min 0 / max 1 replica → ~$0 idle), links it in
the PR description, and tears it down — striking the link through — when the PR
closes or the label is removed. Preview apps migrate themselves on cold start
(single replica, so no race).

**Database:**
- Set a repo **secret** `PREVIEW_DATABASE_URL` to point previews at a real database
  (e.g. a shared dev Postgres).
- **If it is not set**, the preview falls back to **ephemeral in-container SQLite**
  and seeds a Django admin. Configure the admin via repo **variables**
  `PREVIEW_ADMIN_USERNAME` (default `admin`) / `PREVIEW_ADMIN_EMAIL` and the repo
  **secret** `PREVIEW_ADMIN_PASSWORD`. **If `PREVIEW_ADMIN_PASSWORD` is unset, a
  strong random password is generated (and masked in logs)** — there is no weak
  default, so admin login is effectively disabled until you set the secret (the app
  is still reachable for anonymous testing). The SQLite DB and seeded user are
  recreated on each cold start, which is fine for a throwaway preview.

> Preview apps use **public (external) ingress** so reviewers can reach them. For
> sensitive previews, add Azure Container Apps authentication or an IP allowlist, or
> set `PREVIEW_ADMIN_PASSWORD` and rely on app-level auth.

## Notes

- For production, restrict the Postgres firewall (the starter allows Azure
  services broadly) and consider Private Endpoints / VNet integration.
- App Service: scale the Plan and Postgres SKUs via the Bicep parameters.
- ACA: tune `minReplicas`/`maxReplicas`/`cpu`/`memory`; `minReplicas=0` trades a
  cold start for near-zero idle cost.
