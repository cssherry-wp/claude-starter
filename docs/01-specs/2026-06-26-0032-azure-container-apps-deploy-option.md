# Spec: Azure Container Apps deploy option for scaffolding-sdlc

**Status:** Draft — pending user review
**Date:** 2026-06-26
**Sub-project:** 1 of 4 (workflow-improvements decomposition). Order: (1) Azure deploy →
(2) issue/autofix automation → (3) PR/issue templates → (4) stack-aware gating.

## Problem

`scaffolding-sdlc` ships one Azure hosting model: **App Service running a Linux container
pulled from ACR** (`templates/azure/`). It is proven in production (`code/lumen` uses exactly
this topology). But it has no scale-to-zero option, coarse autoscaling, and canary/blue-green
needs deployment slots.

We want a second, opt-in hosting model — **Azure Container Apps (ACA)** — that reuses the same
container image and backing services but adds serverless economics (scale-to-zero), fine-grained
HTTP autoscaling, and native revision/traffic-splitting.

The reference app `django_app-main` uses an Oryx/`azd` code-based model; we explicitly **do not**
adopt that (no container parity, weak local==prod, native-deps pain). Container/ACR stays the
default; ACA is the alternative.

## Goals

1. Offer **App Service (container)** vs **Azure Container Apps** as a hosting choice in the
   scaffolder. The App Service path keeps its current behavior.
2. ACA path reuses the shared `Dockerfile` / `.dockerignore` / `docker-compose.yml`, `acr.bicep`,
   `postgres.bicep`, and the existing Azure OIDC secrets.
3. Migrations on ACA run via a **dedicated, independently-invocable ACA Job** (not the container
   entrypoint), because multiple replicas would otherwise race.
4. Bicep is lint-validated in CI, wired so `local == CI`.

## Non-goals

- Changing the App Service path's *behavior* (only its deploy-workflow filename changes — see below).
- The Oryx/`azd` model.
- The broader CI restructure (split `ci.yml` into per-stack path-filtered workflows) and the
  frontend/e2e make-consistency fix — tracked separately in
  `2026-06-26-0032-ci-restructure-and-make-consistency.md`.

## Design

### 1. Hosting choice (scaffolder)

`SKILL.md` step 6 (Hosting) becomes a **compute choice**:

- **App Service (container)** — turnkey web conveniences (Easy Auth, managed certs, slots);
  always-on. *Default / recommended for a single public web app.*
- **Azure Container Apps** — scale-to-zero economics, automatic HTTP autoscaling, native
  revisions/traffic-splitting; cold starts when scaled to zero.

One line of trade-off each. The scaffolder copies the matching `main.*.bicep` + modules +
parameter files + deploy workflow. Both share the Dockerfile/compose, `acr.bicep`, `postgres.bicep`,
and OIDC secrets.

### 2. Infra (Bicep)

`main.bicep` (App Service) is unchanged. Add a parallel **`main.aca.bicep`** wiring `acr.bicep` +
`postgres.bicep` (shared) + three new modules under `templates/azure/infra/modules/`:

- **`containerenv.bicep`** — Log Analytics workspace + ACA **managed environment**.
- **`containerapp.bicep`** — the container app:
  - external ingress on `8000`, system-assigned identity with **AcrPull** on the registry;
  - `DATABASE_URL` app setting (from Postgres module outputs);
  - **`RUN_MIGRATIONS_ON_START=false`** app setting (entrypoint must not migrate on ACA);
  - `minReplicas` / `maxReplicas` params — **default `minReplicas=1` (always-warm)**, overridable
    to `0` for scale-to-zero; `cpu` / `memory` params.
- **`migration-job.bicep`** — a **manual-trigger** ACA Job sharing the same image, env, and identity,
  with an **overridable `command` param defaulting to `migrate --noinput`**. Doubles as the general
  one-off management-command runner (`createsuperuser`, `loaddata`, contract migrations, etc. — see
  `Notes/.../When to Re-run Django Migrations Separately (ACA Job).md`).

New ACA parameter files: `templates/azure/infra/parameters/aca.{dev,staging,prod}.parameters.json`
(replicas/cpu/memory instead of `appServiceSku`).

### 3. Entrypoint / migration toggle

The shared `startup.sh` currently runs `migrate` then `gunicorn`. Guard the migrate step with
**`RUN_MIGRATIONS_ON_START`** (default `true`):

- **App Service (container)** — `true`. Single instance, so entrypoint migrate is safe (current behavior).
- **ACA** — `false` (set by `containerapp.bicep`). The migration Job owns migrations.

One Dockerfile / one `startup.sh` serves both. The value is fixed at provision time, never flipped by hand.

### 4. CD — `cd.yml`

A repo picks one hosting model, so it gets exactly **one `.github/workflows/cd.yml`**. Template sources:

- `templates/azure/workflows/cd.appservice.yml` — the current `azure-deploy.yml` content, behavior
  unchanged (**renamed** so the deployed file is `cd.yml`).
- `templates/azure/workflows/cd.aca.yml` — new. Gated on `vars.AZURE_CONTAINERAPP_NAME != ''`
  (no-op until configured). Steps:
  1. OIDC login (`azure/login`).
  2. `az acr build` → build image in ACR (same as App Service path).
  3. **Run the migration Job and wait** — `az containerapp job start` then poll the execution to
     completion. **If it fails, stop** — do not route traffic to a new image against an un-migrated schema.
  4. `az containerapp update --image …` → new revision; single-revision mode auto-routes traffic.

The scaffolder copies whichever variant to `.github/workflows/cd.yml`.

### 5. CI — bicep lint

- Add a **`lint-infra`** Make target (runs `az bicep build` over `infra/*.bicep`; no-op when no
  `infra/`), and add it as a dependency of **`make lint`** and **`make check`** so `local == CI`
  picks it up automatically. (Granular target across all stack Makefiles that get a hosting layer.)
- Add **`templates/github/workflows/ci-infra.yml`** — triggered on PRs touching **`infra/**`** only
  (no skipped-step noise), runs `make lint-infra`. The scaffolder copies it **only when the
  hosting/infra layer is added**. The existing monolithic `ci.yml` is **not** modified.

### 6. HOSTING.md

Add an **ACA section**: provisioning `main.aca.bicep`, the `minReplicas` scaling override, how the
migration Job runs automatically on deploy, and how to invoke it manually
(`az containerapp job start … --command …`) for the re-run scenarios. Document new repo vars/secrets.

### 7. Secrets / variables / labels

- Reuse: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (OIDC).
- New repo **variables**: `AZURE_RESOURCE_GROUP`, `AZURE_ACR_NAME`, `AZURE_CONTAINERAPP_NAME`,
  `AZURE_CONTAINERAPP_JOB`.
- New label: **`automation-deploy-test`** (added to `scripts/ensure-labels.sh`) — opts a PR into the
  ephemeral preview environment (§8).

### 8. Ephemeral preview environment (`automation-deploy-test` label) — ACA only

When a PR carries the **`automation-deploy-test`** label, deploy a throwaway ACA instance for manual
testing, link it in the PR, and tear it down when the PR closes (updating the description of the PR with link strikethrough). Scale-to-zero makes this nearly
free: an idle preview costs ~$0 while the PR sits open.

New workflow **`cd-preview.yml`** (copied only on the ACA path), gated on
`vars.AZURE_CONTAINERAPP_NAME != ''` and **same-repo PRs only** (forks get no secrets — mirrors the
`code-review.yml` gate). Triggers on `pull_request` `[labeled, synchronize, reopened]` and `[closed]`.

- **On labeled / synchronize (label present):**
  1. OIDC login; `az acr build` a PR-tagged image (`:pr-<number>`).
  2. Deploy/update a uniquely-named container app **`<app>-pr-<number>`** with
     **`minReplicas=0`, `maxReplicas=1`** in the ACA environment. The single replica
     **self-migrates on cold start** (`RUN_MIGRATIONS_ON_START=true`) — no Job needed, no race.
     Database per the resolved strategy in Risks (`PREVIEW_DATABASE_URL`, else SQLite + seeded admin).
  3. Edit the PR **description** to insert/update a marked block with the preview URL
     (idempotent — `<!-- preview-env:start -->`/`:end` markers so re-runs replace, not append).
- **On PR `closed` (merged or not):** `az containerapp delete` the `<app>-pr-<number>` app and any
  preview-only resources, and Add strikethrough to all lines between the marker block.

If the label is removed mid-PR, treat it like `closed` for that app (delete + unlink).

## Testing & validation

- `az bicep build` on `main.aca.bicep` and each new module (the `lint-infra` target — first Bicep
  test in the plugin).
- Documented smoke test: deploy `main.aca.bicep` to a `dev` env, confirm the migration Job succeeds
  and the app URL serves.

## Risks / assumptions

- ACA Bicep surface (`Microsoft.App/containerApps` + managed environment + Log Analytics) is more
  verbose and newer than App Service; the lint gate mitigates malformed templates but not semantic
  misconfig.
- Always-warm default means the scale-to-zero cost win is opt-in; documented in HOSTING.md.
- Assumes the Django app is stateless enough for multiple replicas (no in-process sessions / local
  disk). Noted in HOSTING.md.
- `az bicep` must be available locally for `make lint-infra` (`az bicep install`); ubuntu CI runners
  have `az` preinstalled.
- **Preview-env database strategy (resolved):** the preview uses `PREVIEW_DATABASE_URL` if set
  (e.g. a shared dev Postgres); **otherwise it falls back to ephemeral in-container SQLite and seeds
  a Django admin** from `PREVIEW_ADMIN_USERNAME`/`PREVIEW_ADMIN_EMAIL` (repo vars) +
  `PREVIEW_ADMIN_PASSWORD` (repo secret), via a `CREATE_SUPERUSER_ON_START` entrypoint toggle. SQLite
  and the seeded user are recreated on each cold start — acceptable for a throwaway preview. A per-PR
  managed Postgres remains a future option if previews need persistence across cold starts.
- **Preview-env leak risk:** if the `closed` teardown run fails, a `<app>-pr-<number>` app lingers.
  Scale-to-zero keeps idle cost ~$0, but a periodic sweep (or a max-age check) may be warranted —
  note for planning.
