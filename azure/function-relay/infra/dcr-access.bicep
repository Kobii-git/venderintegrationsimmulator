param dcrName string
param principalId string
resource dcr 'Microsoft.Insights/dataCollectionRules@2023-03-11' existing = {
  name: dcrName
}
resource publisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(dcr.id, principalId, 'Monitoring Metrics Publisher')
  scope: dcr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
