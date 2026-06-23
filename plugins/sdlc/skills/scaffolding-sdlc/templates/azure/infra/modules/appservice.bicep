@description('Web App name (globally unique).')
param appName string

@description('Azure region.')
param location string

@description('ACR login server, e.g. myregistry.azurecr.io.')
param acrLoginServer string

@description('Container image (repository:tag) within the registry.')
param imageName string

@description('Postgres FQDN.')
param postgresHost string

@description('Postgres database name.')
param postgresDb string

@description('Postgres user.')
param postgresUser string

@secure()
@description('Postgres password.')
param postgresPassword string

@description('App Service Plan SKU.')
param sku string = 'B1'

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: 'plan-${appName}'
  location: location
  sku: { name: sku }
  kind: 'linux'
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux,container'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|${acrLoginServer}/${imageName}'
      acrUseManagedIdentityCreds: true
      appSettings: [
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'DJANGO_ALLOWED_HOSTS', value: '${appName}.azurewebsites.net' }
        {
          name: 'DATABASE_URL'
          value: 'postgresql://${postgresUser}:${postgresPassword}@${postgresHost}:5432/${postgresDb}'
        }
      ]
    }
  }
}

output principalId string = app.identity.principalId
output defaultHostname string = app.properties.defaultHostName
