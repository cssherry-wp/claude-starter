@description('Migration/one-off Job name.')
param jobName string

@description('Azure region.')
param location string

@description('Container Apps managed environment resource ID.')
param environmentId string

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

@description('manage.py command to run. Defaults to migrate; override to run any one-off management command (createsuperuser, loaddata, a contract migration, etc.).')
param command string = 'migrate --noinput'

@description('vCPU for the job replica.')
param cpu string = '0.5'

@description('Memory for the job replica.')
param memory string = '1.0Gi'

@description('Max seconds a replica may run before timing out.')
param replicaTimeout int = 1800

var databaseUrl = 'postgresql://${postgresUser}:${postgresPassword}@${postgresHost}:5432/${postgresDb}'

// A manual-trigger Job: provisioned once, invoked on demand via
//   az containerapp job start --name <jobName> -g <rg>
// or with a per-run command override via --command. The deploy workflow starts it
// (with the default migrate command) before routing traffic to a new revision.
resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: replicaTimeout
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
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
          name: 'migrate'
          image: '${acrLoginServer}/${imageName}'
          command: ['/bin/sh', '-c']
          args: ['python manage.py ${command}']
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
          ]
        }
      ]
    }
  }
}

output principalId string = job.identity.principalId
output name string = job.name
