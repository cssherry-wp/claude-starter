@description('PostgreSQL Flexible Server name (globally unique).')
param serverName string

@description('Azure region.')
param location string

@description('Administrator username.')
param adminUser string

@secure()
@description('Administrator password.')
param adminPassword string

@description('Initial database name.')
param databaseName string

@description('SKU name (Burstable tier).')
param sku string = 'Standard_B1ms'

@description('Storage size in GB.')
param storageSizeGB int = 32

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: serverName
  location: location
  sku: {
    name: sku
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: adminUser
    administratorLoginPassword: adminPassword
    version: '16'
    storage: { storageSizeGB: storageSizeGB }
    backup: { backupRetentionDays: 7 }
    highAvailability: { mode: 'Disabled' }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: server
  name: databaseName
}

// Allow other Azure services (the App Service) to reach the server.
resource allowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: server
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output fqdn string = server.properties.fullyQualifiedDomainName
output databaseName string = databaseName
