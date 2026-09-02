#requires -Version 5.1
<#
QCFP-MTF One-Click Review Bundle Builder
========================================

Purpose
-------
One-click generation and verification of both official QCFP-MTF review bundles:

1. code-review bundle + sidecar manifest
2. governance-review bundle + sidecar manifest
3. offline verification for both bundles
4. verification logs
5. final PASS/FAIL summary

This wrapper does NOT modify qcfp_project_code_merger.py.
It only calls its official CLI.

Expected project layout
-----------------------
<ProjectRoot>\
  qcfp_project_code_merger.py
  Core\
  Merged_Code\

Usage
-----
PowerShell:
  .\build_qcfp_review_bundles.ps1

If PowerShell execution policy blocks local scripts:
  powershell -ExecutionPolicy Bypass -File .\build_qcfp_review_bundles.ps1

Optional:
  .\build_qcfp_review_bundles.ps1 `
      -ProjectRoot "C:\Users\Quansheng\Documents\projects\TA_Workflow" `
      -PythonExe "python" `
      -MergerScript "qcfp_project_code_merger.py"
#>

[CmdletBinding()]
param(
    [string]$ProjectRoot = "C:\Users\Quansheng\Documents\projects\TA_Workflow",
    [string]$PythonExe = "python",
    [string]$MergerScript = "qcfp_project_code_merger.py"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 88)
    Write-Host $Title
    Write-Host ("=" * 88)
}

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StepName,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [string]$LogFile = ""
    )

    Write-Host ""
    Write-Host "[RUN] $StepName"
    Write-Host ("      " + $PythonExe + " " + (($Arguments | ForEach-Object {
        if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
    }) -join " "))

    if ($LogFile) {
        $output = & $PythonExe @Arguments 2>&1
        $exitCode = $LASTEXITCODE

        $output | Tee-Object -FilePath $LogFile

        if ($exitCode -ne 0) {
            throw "$StepName failed with exit code $exitCode. See: $LogFile"
        }
    }
    else {
        & $PythonExe @Arguments
        $exitCode = $LASTEXITCODE

        if ($exitCode -ne 0) {
            throw "$StepName failed with exit code $exitCode."
        }
    }
}

function Assert-FileExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description not found: $Path"
    }
}

function Assert-VerifiedLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LogFile,

        [Parameter(Mandatory = $true)]
        [string]$Profile
    )

    $text = Get-Content -LiteralPath $LogFile -Raw

    if ($text -notmatch 'BUNDLE_VERIFIED') {
        throw "$Profile verification log does not contain BUNDLE_VERIFIED: $LogFile"
    }

    if ($text -match 'BUNDLE_VERIFICATION_FAILED') {
        throw "$Profile verification log contains BUNDLE_VERIFICATION_FAILED: $LogFile"
    }
}

try {
    Write-Section "QCFP-MTF One-Click Review Bundle Builder"

    $ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)

    if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
        throw "ProjectRoot does not exist: $ProjectRoot"
    }

    Set-Location -LiteralPath $ProjectRoot

    $MergerPath = Join-Path $ProjectRoot $MergerScript
    Assert-FileExists -Path $MergerPath -Description "Merger script"

    # Confirm Python is callable.
    Write-Host "[CHECK] Python"
    & $PythonExe --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python executable failed: $PythonExe"
    }

    # Compile-check the frozen merger before using it.
    Write-Host "[CHECK] qcfp_project_code_merger.py syntax"
    & $PythonExe -m py_compile $MergerPath
    if ($LASTEXITCODE -ne 0) {
        throw "py_compile failed for: $MergerPath"
    }
    Write-Host "[PASS] Merger syntax check"

    $MergedDir = Join-Path $ProjectRoot "Merged_Code"
    New-Item -ItemType Directory -Path $MergedDir -Force | Out-Null

    # --output is the BASE name. qcfp_project_code_merger.py appends
    # .code-review or .governance-review automatically.
    $OutputBase = Join-Path $MergedDir "merged_code_QCFP-MTF.txt"

    $CodeBundle = Join-Path $MergedDir "merged_code_QCFP-MTF.code-review.txt"
    $CodeManifest = Join-Path $MergedDir "merged_code_QCFP-MTF.code-review.manifest.json"
    $CodeVerifyLog = Join-Path $MergedDir "verify_code-review.txt"

    $GovBundle = Join-Path $MergedDir "merged_code_QCFP-MTF.governance-review.txt"
    $GovManifest = Join-Path $MergedDir "merged_code_QCFP-MTF.governance-review.manifest.json"
    $GovVerifyLog = Join-Path $MergedDir "verify_governance-review.txt"

    # ---------------------------------------------------------------------
    # 1. Build code-review
    # ---------------------------------------------------------------------
    Write-Section "1/4 Build code-review Bundle"

    Invoke-PythonStep `
        -StepName "Build code-review" `
        -Arguments @(
            $MergerPath,
            "--profile", "code-review",
            "--output", $OutputBase
        )

    Assert-FileExists -Path $CodeBundle -Description "code-review bundle"
    Assert-FileExists -Path $CodeManifest -Description "code-review manifest"

    # ---------------------------------------------------------------------
    # 2. Verify code-review
    # ---------------------------------------------------------------------
    Write-Section "2/4 Verify code-review Bundle"

    Invoke-PythonStep `
        -StepName "Verify code-review" `
        -Arguments @(
            $MergerPath,
            "--verify", $CodeBundle,
            "--manifest", $CodeManifest
        ) `
        -LogFile $CodeVerifyLog

    Assert-VerifiedLog -LogFile $CodeVerifyLog -Profile "code-review"

    # ---------------------------------------------------------------------
    # 3. Build governance-review
    # ---------------------------------------------------------------------
    Write-Section "3/4 Build governance-review Bundle"

    Invoke-PythonStep `
        -StepName "Build governance-review" `
        -Arguments @(
            $MergerPath,
            "--profile", "governance-review",
            "--output", $OutputBase
        )

    Assert-FileExists -Path $GovBundle -Description "governance-review bundle"
    Assert-FileExists -Path $GovManifest -Description "governance-review manifest"

    # ---------------------------------------------------------------------
    # 4. Verify governance-review
    # ---------------------------------------------------------------------
    Write-Section "4/4 Verify governance-review Bundle"

    Invoke-PythonStep `
        -StepName "Verify governance-review" `
        -Arguments @(
            $MergerPath,
            "--verify", $GovBundle,
            "--manifest", $GovManifest
        ) `
        -LogFile $GovVerifyLog

    Assert-VerifiedLog -LogFile $GovVerifyLog -Profile "governance-review"

    # ---------------------------------------------------------------------
    # Final evidence summary
    # ---------------------------------------------------------------------
    Write-Section "FINAL RESULT"

    $MergerSha = (Get-FileHash -LiteralPath $MergerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $CodeSha = (Get-FileHash -LiteralPath $CodeBundle -Algorithm SHA256).Hash.ToLowerInvariant()
    $GovSha = (Get-FileHash -LiteralPath $GovBundle -Algorithm SHA256).Hash.ToLowerInvariant()

    $SummaryPath = Join-Path $MergedDir "review_bundle_build_summary.txt"

    $summary = @"
QCFP-MTF REVIEW BUNDLE BUILD SUMMARY
====================================

STATUS:
PASS

MERGER:
$MergerPath
SHA256:
$MergerSha

CODE REVIEW:
Bundle   : $CodeBundle
Manifest : $CodeManifest
Verify   : $CodeVerifyLog
SHA256   : $CodeSha
Verdict  : BUNDLE_VERIFIED

GOVERNANCE REVIEW:
Bundle   : $GovBundle
Manifest : $GovManifest
Verify   : $GovVerifyLog
SHA256   : $GovSha
Verdict  : BUNDLE_VERIFIED

READY FOR REVIEW:
TRUE
"@

    $summary | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

    Write-Host "[PASS] code-review       : BUNDLE_VERIFIED"
    Write-Host "[PASS] governance-review : BUNDLE_VERIFIED"
    Write-Host ""
    Write-Host "Generated files:"
    Write-Host "  $CodeBundle"
    Write-Host "  $CodeManifest"
    Write-Host "  $CodeVerifyLog"
    Write-Host "  $GovBundle"
    Write-Host "  $GovManifest"
    Write-Host "  $GovVerifyLog"
    Write-Host "  $SummaryPath"
    Write-Host ""
    Write-Host "READY FOR REVIEW: TRUE"
    exit 0
}
catch {
    Write-Host ""
    Write-Host ("=" * 88)
    Write-Host "QCFP-MTF REVIEW BUNDLE BUILD FAILED"
    Write-Host ("=" * 88)
    Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "No formal review should use the output until this error is resolved."
    exit 1
}
