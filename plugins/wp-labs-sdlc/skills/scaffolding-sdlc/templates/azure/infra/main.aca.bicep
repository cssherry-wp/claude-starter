// Azure starter infra (Container Apps variant): ACR + Postgres + Container Apps
// environment + Container App + migration Job.
// Deploy: az deployment group create -g <rg> -f infra/main.aca.bicep \
//           -p infra/parameters/aca.<env>.parameters.json -p pgAdminPassword=<secret>

@description('Application name; prefixes all resources.')
param appName string

@description('Environment name.')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'prod'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Container image (repository:tag) to deploy from the registry. Defaults to <appName>:<environment>; CD overrides the tag per build.')
param imageName string = '${appName}:${environment}'

@description('PostgreSQL administrator username.')
param pgAdminUser string = 'psqladmin'

@secure()
@description('PostgreSQL administrator password.')
param pgAdminPassword string

@description('Minimum replicas (0 = scale-to-zero). Default 1 keeps the app always-warm.')
@minValue(0)
param minReplicas int = 1

@description('Maximum replicas.')
@minValue(1)
param maxReplicas int = 3

@description('vCPU per replica.')
param cpu string = '0.5'

@description('Memory per replica.')
param memory string = '1.0Gi'

@description('PostgreSQL SKU.')
param postgresSku string = 'Standard_B1ms'

var acrName = toLower(replace('acr${appName}${environment}', '-', ''))

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    name: acrName
    location: location
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    serverName: 'psql-${appName}-${environment}'
    location: location
    adminUser: pgAdminUser
    adminPassword: pgAdminPassword
    databaseName: 'app'
    sku: postgresSku
  }
}

module containerenv 'modules/containerenv.bicep' = {
  name: 'containerenv'
  params: {
    name: 'cae-${appName}-${environment}'
    location: location
  }
}

// Built once here so the Postgres DSN format lives in a single place; both the app
// and the migration Job receive it as an opaque secret.
var databaseUrl = 'postgresql://${pgAdminUser}:${pgAdminPassword}@${postgres.outputs.fqdn}:5432/${postgres.outputs.databaseName}'

module containerapp 'modules/containerapp.bicep' = {
  name: 'containerapp'
  params: {
    appName: '${appName}-${environment}'
    location: location
    environmentId: containerenv.outputs.environmentId
    environmentDefaultDomain: containerenv.outputs.defaultDomain
    acrLoginServer: acr.outputs.loginServer
    imageName: imageName
    databaseUrl: databaseUrl
    minReplicas: minReplicas
    maxReplicas: maxReplicas
    cpu: cpu
    memory: memory
  }
}

module migrationJob 'modules/migration-job.bicep' = {
  name: 'migration-job'
  params: {
    jobName: 'job-${appName}-${environment}-migrate'
    location: location
    environmentId: containerenv.outputs.environmentId
    acrLoginServer: acr.outputs.loginServer
    imageName: imageName
    databaseUrl: databaseUrl
  }
}

// Both the app and the migration Job pull images from ACR via their managed
// identities, so each needs AcrPull. The role assignment is created in the same
// deployment; ACA retries the initial pull until the assignment propagates.
resource acrResource 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

// Two explicit assignments (not a for-loop): the principal IDs are module outputs,
// which Bicep cannot use to size a resource loop (BCP178).
resource appAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResource.id, '${appName}-${environment}', 'app', 'AcrPull')
  scope: acrResource
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: containerapp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource jobAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResource.id, '${appName}-${environment}', 'job', 'AcrPull')
  scope: acrResource
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: migrationJob.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

output webAppUrl string = 'https://${containerapp.outputs.fqdn}'
output acrLoginServer string = acr.outputs.loginServer
output containerAppName string = containerapp.outputs.name
output migrationJobName string = migrationJob.outputs.name
