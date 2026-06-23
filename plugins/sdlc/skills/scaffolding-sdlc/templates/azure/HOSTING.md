# Hosting

How to run the app in a container locally and deploy it to Azure. The
scaffolding-sdlc skill copies the stack's `Dockerfile`, `.dockerignore`, and
`docker-compose.yml` to the repo root, the Bicep under `infra/`, and
`azure-deploy.yml` into `.github/workflows/`.

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

### 2. Wire up CI deploy (`azure-deploy.yml`)

The workflow builds the image in ACR and points the Web App at it on every push
to `main`. Configure once:

- **OIDC federated credentials** for a Microsoft Entra app/service principal
  with access to the resource group, then add repo **secrets**:
  `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- Repo **variables**: `AZURE_RESOURCE_GROUP`, `AZURE_ACR_NAME`,
  `AZURE_WEBAPP_NAME`.

The deploy job is gated on `AZURE_WEBAPP_NAME` — until you set it, the workflow
no-ops, so it's safe to merge before Azure is set up.

## Notes

- For production, restrict the Postgres firewall (the starter allows Azure
  services broadly) and consider Private Endpoints / VNet integration.
- Scale the App Service Plan and Postgres SKUs via the Bicep parameters.
