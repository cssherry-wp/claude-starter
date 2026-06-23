// Azure starter infra: ACR + Postgres + App Service (Linux container).
// Deploy: az deployment group create -g <rg> -f infra/main.bicep \
//           -p infra/parameters/<env>.parameters.json -p pgAdminPassword=<secret>

@description('Application name; prefixes all resources.')
param appName string

@description('Environment name.')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'prod'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Container image (repository:tag) to deploy from the registry.')
param imageName string

@description('PostgreSQL administrator username.')
param pgAdminUser string = 'psqladmin'

@secure()
@description('PostgreSQL administrator password.')
param pgAdminPassword string

@description('App Service Plan SKU.')
param appServiceSku string = 'B1'

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

module appservice 'modules/appservice.bicep' = {
  name: 'appservice'
  params: {
    appName: '${appName}-${environment}'
    location: location
    acrLoginServer: acr.outputs.loginServer
    imageName: imageName
    postgresHost: postgres.outputs.fqdn
    postgresDb: postgres.outputs.databaseName
    postgresUser: pgAdminUser
    postgresPassword: pgAdminPassword
    sku: appServiceSku
  }
}

// Let the web app pull images from ACR via its managed identity (AcrPull).
resource acrResource 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResource.id, '${appName}-${environment}', 'AcrPull')
  scope: acrResource
  properties: {
    // AcrPull built-in role.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: appservice.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

output webAppUrl string = 'https://${appservice.outputs.defaultHostname}'
output acrLoginServer string = acr.outputs.loginServer
