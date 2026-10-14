<#
  setup-foundry.ps1  -  Inside the Game hackathon
  Creates: resource group -> Foundry resource -> Foundry project -> model deployment
           -> gives YOU keyless (Entra ID) access -> writes .env for the smoke test.

  Run from PowerShell:
      az login
      powershell -ExecutionPolicy Bypass -File .\setup-foundry.ps1

  Requires Azure CLI 2.80.0 or later (check: az version  |  update: az upgrade)
#>

# ===== 1. EDIT THESE =====
$RG            = "rg-insidethegame"
$LOC           = "eastus"               # must be a region your subscription allows (step 0 shows it)
$RES = "itg-foundry-jeffy1410"  # globally unique: lowercase letters, numbers, hyphens
$PROJ          = "insidethegame"
$MODEL         = "gpt-5-mini"
$MODEL_VERSION = "2025-08-07"           # step 0 lists the versions offered in $LOC
$SKU           = "GlobalStandard"
$CAPACITY      = 10                     # thousands of tokens per minute

function Check([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "Stopped at: $step (see the az error above)" }
}

# ===== 0. DIAGNOSE THE SUBSCRIPTION =====
Write-Host "`n== Signed-in subscription ==" -ForegroundColor Cyan
az account show --query "{subscription:name, user:user.name}" -o table
Check "az account show - run 'az login' first"

Write-Host "`n== Offer type (AzureForStudents / FreeTrial / PayAsYouGo ...) ==" -ForegroundColor Cyan
az rest --method get --url "https://management.azure.com/subscriptions/{subscriptionId}?api-version=2022-12-01" --query "subscriptionPolicies.quotaId" -o tsv

Write-Host "`n== Policy assignments (look for an allowed-regions list) ==" -ForegroundColor Cyan
az policy assignment list --disable-scope-strict-match --query "[].{name:displayName, parameters:parameters}" -o json

Write-Host "`n== Is $MODEL offered in $LOC ? ==" -ForegroundColor Cyan
az cognitiveservices model list --location $LOC --query "[?model.name=='$MODEL'].{version:model.version, skus:join(', ', model.skus[].name)}" -o table

Read-Host "`nIf the offer is Students/FreeTrial and a policy lists allowed regions, set `$LOC to one of them and re-run. Press Enter to continue, or Ctrl+C to stop"

# ===== 2. RESOURCE GROUP =====
Write-Host "`n== Creating resource group $RG in $LOC ==" -ForegroundColor Cyan
az group create --name $RG --location $LOC -o none
Check "resource group"

# ===== 3. FOUNDRY RESOURCE (managed identity + project management; cannot be changed later) =====
Write-Host "`n== Creating Foundry resource $RES ==" -ForegroundColor Cyan
az cognitiveservices account create `
    --name $RES `
    --resource-group $RG `
    --kind AIServices `
    --sku S0 `
    --location $LOC `
    --custom-domain $RES `
    --assign-identity `
    --allow-project-management true `
    -o none
Check "Foundry resource (CustomDomainInUse = choose another name; RequestDisallowedByAzure = region not allowed)"

# ===== 4. FOUNDRY PROJECT =====
Write-Host "`n== Creating Foundry project $PROJ ==" -ForegroundColor Cyan
az cognitiveservices account project create `
    --name $RES `
    --resource-group $RG `
    --project-name $PROJ `
    --location $LOC `
    -o none
Check "Foundry project"

# ===== 5. MODEL DEPLOYMENT =====
Write-Host "`n== Deploying $MODEL ($SKU, $CAPACITY K TPM) ==" -ForegroundColor Cyan
az cognitiveservices account deployment create `
    --name $RES `
    --resource-group $RG `
    --deployment-name $MODEL `
    --model-name $MODEL `
    --model-version $MODEL_VERSION `
    --model-format OpenAI `
    --sku-name $SKU `
    --sku-capacity $CAPACITY `
    -o none
Check "model deployment (DeploymentModelNotSupported = wrong region/version/SKU; quota error = request quota)"

# ===== 6. KEYLESS ACCESS FOR YOU (Foundry User role, formerly 'Azure AI User') =====
Write-Host "`n== Granting you the Foundry User role on the project ==" -ForegroundColor Cyan
$PROJECT_ID = az cognitiveservices account project show `
    --name $RES `
    --resource-group $RG `
    --project-name $PROJ `
    --query id -o tsv
Check "read project id"

$ME = az ad signed-in-user show --query id -o tsv
Check "read your user id"

az role assignment create `
    --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" `
    --assignee-object-id $ME `
    --assignee-principal-type User `
    --scope $PROJECT_ID `
    -o none
Check "role assignment"

# ===== 7. WRITE .env FOR THE SMOKE TEST (no keys - just the endpoint) =====
$ENDPOINT = "https://$RES.services.ai.azure.com/api/projects/$PROJ"
Set-Content -Path ".env" -Encoding ascii -Value @(
    "FOUNDRY_PROJECT_ENDPOINT=$ENDPOINT",
    "FOUNDRY_MODEL=$MODEL"
)

Write-Host "`nDone. Project endpoint: $ENDPOINT" -ForegroundColor Green
Write-Host "Role assignments can take a few minutes to apply. Then run:  uv run smoke_test.py"
