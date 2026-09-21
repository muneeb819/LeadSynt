<#
.SYNOPSIS
Verifies the deployed LeadSynt backend health endpoints on Vercel.

.DESCRIPTION
Hits GET {BaseUrl}/api/v1/health and /api/v1/health/ready against the Vercel
"backend" project deployment and reports one of three observable outcomes per
endpoint:

  - HEALTHY  200 + JSON body -> prints status/version/environment/checks
  - PROTECTED                -> Vercel Deployment Protection login page (SSO)
  - CRASHED  500 + FUNCTION_INVOCATION_FAILED -> serverless cold-start crash

Exits 0 when every checked endpoint is healthy, 1 otherwise (scriptable for CI).

.PARAMETER BaseUrl
Base URL of the deployed backend. Defaults to the stable project domain of the
Vercel "backend" project (backend-two-ruddy-64.vercel.app). Pass a per-deployment
alias (e.g. https://backend-git-main-muneeb819s-projects.vercel.app) to probe a
specific build.

.PARAMETER TimeoutSec
Per-request timeout in seconds (default 30).

.EXAMPLE
.\scripts\verify-backend-health.ps1

.EXAMPLE
.\scripts\verify-backend-health.ps1 -BaseUrl "https://backend-git-main-muneeb819s-projects.vercel.app"
#>
param(
    [string]$BaseUrl = "https://backend-two-ruddy-64.vercel.app",
    [int]$TimeoutSec = 30
)

$ErrorActionPreference = "Stop"

function Invoke-Verify {
    param([string]$Url, [int]$TimeoutSec)
    try {
        $resp = Invoke-WebRequest -Method Get -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing
        $ct = ""
        if ($resp.Headers["Content-Type"]) { $ct = [string]$resp.Headers["Content-Type"] }
        return [pscustomobject]@{ Url = $Url; HttpStatus = [int]$resp.StatusCode; ContentType = $ct; Body = [string]$resp.Content; Ok = $true }
    }
    catch {
        $code = $null
        if ($_.Exception.Response) { $code = $_.Exception.Response.StatusCode.value__ }
        $body = ""
        try { $body = [string]$_.ErrorDetails.Message } catch { }
        return [pscustomobject]@{ Url = $Url; HttpStatus = $code; ContentType = ""; Body = $body; Ok = $false }
    }
}

function Test-HealthyJson {
    param($r)
    if (-not $r.Ok) { return $false }
    if ($r.HttpStatus -ne 200) { return $false }
    if ($r.ContentType -notmatch "json") { return $false }
    try { $null = $r.Body | ConvertFrom-Json; return $true } catch { return $false }
}

$paths = @("/api/v1/health", "/api/v1/health/ready")
$results = foreach ($p in $paths) { Invoke-Verify -Url "$BaseUrl$p" -TimeoutSec $TimeoutSec }

$overall = 0
foreach ($r in $results) {
    $label = "GET $($r.Url)"
    if (Test-HealthyJson $r) {
        $json = $r.Body | ConvertFrom-Json
        if ($r.Url -like "*health/ready") {
            "OK      $label -> status=$($json.status)"
        }
        else {
            "OK      $label -> status=$($json.status) version=$($json.version) env=$($json.environment)"
            "         checks: db=$($json.checks.database) redis=$($json.checks.redis)"
        }
    }
    elseif ($r.Body -match "FUNCTION_INVOCATION_FAILED" -or ($r.HttpStatus -ge 500)) {
        $why = if ($r.Body -match "FUNCTION_INVOCATION_FAILED") { "FUNCTION_INVOCATION_FAILED" } else { "cold-start error" }
        "FAIL    $label -> HTTP $($r.HttpStatus) serverless invocation crashed ($why)"
        $overall = 1
    }
    elseif ($r.HttpStatus -in 401,403,307 -or $r.Body -match "Protected Deployment|Deployment Protection|javascript-challenge") {
        "FAIL    $label -> HTTP $($r.HttpStatus) blocked by Vercel Deployment Protection (login page returned)"
        $overall = 1
    }
    elseif (-not $r.Ok) {
        "FAIL    $label -> network/HTTP error (HTTP = $($r.HttpStatus))"
        $overall = 1
    }
    else {
        "UNKNOWN $label -> HTTP $($r.HttpStatus) content-type=$($r.ContentType) (not a JSON health response)"
        $overall = 1
    }
}

if ($overall -eq 0) { "VERDICT: backend healthy on $BaseUrl" }
else { "VERDICT: backend NOT healthy on $BaseUrl (see per-endpoint results above)" }
exit $overall