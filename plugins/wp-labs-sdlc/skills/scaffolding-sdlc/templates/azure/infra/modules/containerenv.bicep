@description('Container Apps managed environment name.')
param name string

@description('Azure region.')
param location string

// Log Analytics backs the managed environment's log/metric ingestion.
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

output environmentId string = environment.id
// `<app>.<defaultDomain>` is the public FQDN; used to set DJANGO_ALLOWED_HOSTS.
output defaultDomain string = environment.properties.defaultDomain
