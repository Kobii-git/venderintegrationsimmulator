@description('Globally unique Function App name.')
param appName string
param location string = resourceGroup().location
@description('Existing public-cloud DCE ingestion endpoint, including https://.')
param dceEndpoint string
@description('Existing DCR resource name, distinct from its immutable ID.')
param dcrName string
param dcrResourceGroup string = resourceGroup().name
param dcrSubscriptionId string = subscription().subscriptionId
param dcrImmutableId string
param dcrStream string = 'Custom-SimulatorEvents'
@description('Existing Log Analytics workspace resource ID for relay diagnostics.')
param workspaceResourceId string

var storageName = 'st${uniqueString(resourceGroup().id, appName)}'
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}
resource packages 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'deployments'
  properties: { publicAccess: 'None' }
}
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${appName}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceResourceId
    DisableLocalAuth: true
  }
}
resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${appName}-plan'
  location: location
  kind: 'functionapp'
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}
resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      minTlsVersion: '1.2'
      appSettings: [
        { name: 'AzureWebJobsStorage__accountName', value: storage.name }
        { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
        { name: 'APPLICATIONINSIGHTS_AUTHENTICATION_STRING', value: 'Authorization=AAD' }
        { name: 'DCE_ENDPOINT', value: dceEndpoint }
        { name: 'DCR_IMMUTABLE_ID', value: dcrImmutableId }
        { name: 'DCR_STREAM', value: dcrStream }
      ]
    }
    functionAppConfig: {
      runtime: { name: 'python', version: '3.12' }
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${packages.name}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: { maximumInstanceCount: 40, instanceMemoryMB: 2048 }
    }
  }
}
// Host secrets/state and deployment packages use the app's identity, never storage keys.
var storageRoles = [
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b' // Storage Blob Data Owner
  '974c5e8b-45b9-4653-ba55-5f855dd0fb88' // Storage Queue Data Contributor
  '17d1049b-9a84-46fb-8f53-869881c3d3ab' // Storage Account Contributor (host diagnostics)
]
resource storageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in storageRoles: {
  name: guid(storage.id, app.id, role)
  scope: storage
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
  }
}]
resource insightsAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(insights.id, app.id, 'metrics')
  scope: insights
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
  }
}
module dcrAccess 'dcr-access.bicep' = {
  name: '${appName}-dcr-access'
  scope: resourceGroup(dcrSubscriptionId, dcrResourceGroup)
  params: { dcrName: dcrName, principalId: app.identity.principalId }
}
output ingestionUrl string = 'https://${app.properties.defaultHostName}/api/ingest'
output healthUrl string = 'https://${app.properties.defaultHostName}/api/health'
