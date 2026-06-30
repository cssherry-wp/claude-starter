@description('Container App name.')
param appName string

@description('Azure region.')
param location string

@description('Container Apps managed environment resource ID.')
param environmentId string

@description('Environment default domain (for DJANGO_ALLOWED_HOSTS).')
param environmentDefaultDomain string

@description('ACR login server, e.g. myregistry.azurecr.io.')
param acrLoginServer string

@description('Container image (repository:tag) within the registry.')
param imageName string

@secure()
@description('Full Postgres connection string (DATABASE_URL), built by the caller.')
param databaseUrl string

@description('Minimum replicas. 0 enables scale-to-zero; default 1 keeps the app always-warm.')
@minValue(0)
param minReplicas int = 1

@description('Maximum replicas.')
@minValue(1)
param maxReplicas int = 3

@description('vCPU per replica.')
param cpu string = '0.5'

@description('Memory per replica.')
param memory string = '1.0Gi'

@description('Container listening port.')
param targetPort int = 8000

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
      }
      // Pull from ACR with the app's system-assigned identity (AcrPull granted in main).
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        // DATABASE_URL embeds the secure password by design (Django reads one URL).
        #disable-next-line use-secure-value-for-secure-inputs
        { name: 'database-url', value: databaseUrl }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: '${acrLoginServer}/${imageName}'
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            // Migrations run via the dedicated ACA Job, never the entrypoint —
            // multiple replicas would otherwise race.
            { name: 'RUN_MIGRATIONS_ON_START', value: 'false' }
            { name: 'DJANGO_ALLOWED_HOSTS', value: '${appName}.${environmentDefaultDomain}' }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output principalId string = app.identity.principalId
output fqdn string = app.properties.configuration.ingress.fqdn
output name string = app.name
