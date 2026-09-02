#requires -Version 5.1
<#
QCFP-MTF One-Click Review Bundle Builder
========================================

Purpose
-------
One-click generation and verification of both official QCFP-MTF source-review bundles:

1. code-review bundle + sidecar manifest
2. governance-review bundle + sidecar manifest
3. offline verification for both bundles
4. verification logs
5. frozen merger identity check
6. project-root identity binding
7. source-manifest change reporting
8. final PASS/FAIL source-review summary

Important boundary
------------------
This wrapper is ONLY for Source Evidence.
It does NOT run Phase 3 regression, Phase 3 gate, baseline promotion,
or create phase3_evidence.zip.

This wrapper does NOT modify qcfp_project_code_merger.py.
It only calls its frozen official CLI.

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

Patch-acceptance mode:
  .\build_qcfp_review_bundles.ps1 -RequireSourceChange

-RequireSourceChange means:
  - a previous code-review/governance-review sidecar must already exist; and
  - at least one source manifest SHA256 must change compared with the previous build.

Normal review mode does NOT fail when source is unchanged; it emits a warning instead.
#>

[CmdletBinding()]
param(
    [string]$ProjectRoot = "C:\Users\Quansheng\Documents\projects\TA_Workflow",
    [string]$PythonExe = "python",
    [string]$MergerScript = "qcfp_project_code_merger.py",
    [switch]$RequireSourceChange
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -----------------------------------------------------------------------------
# Frozen identities
# -----------------------------------------------------------------------------
# qcfp_project_code_merger.py is a frozen governance artifact.
# Do NOT change this value unless the frozen merger itself has gone through a
# formal defect/change-request, independent acceptance, and re-freeze process.
$ExpectedMergerSha256 = "486bed0a9f5fe824b826939e7bd118a1c508a8430d27ab1b9be1d07631e6555a"

# The frozen merger itself contains this PROJECT_ROOT.  The wrapper must bind to
# the same root so that "requested root" cannot differ from "actual scanned root".
$ExpectedProjectRoot = "C:\Users\Quansheng\Documents\projects\TA_Workflow"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 88)
    Write-Host $Title
    Write-Host ("=" * 88)
}

function Normalize-PathForCompare {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $full = [System.IO.Path]::GetFullPath($Path)
    return $full.TrimEnd([char[]]@('\', '/'))
}

function Test-PathEqual {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Left,

        [Parameter(Mandatory = $true)]
        [string]$Right
    )

    $leftNorm = Normalize-PathForCompare -Path $Left
    $rightNorm = Normalize-PathForCompare -Path $Right

    return [string]::Equals(
        $leftNorm,
        $rightNorm,
        [System.StringComparison]::OrdinalIgnoreCase
    )
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

function Get-ManifestIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath,

        [switch]$AllowMissing
    )

    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        if ($AllowMissing) {
            return $null
        }
        throw "Manifest not found: $ManifestPath"
    }

    try {
        $obj = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    }
    catch {
        throw "Manifest JSON parse failed: $ManifestPath ; $($_.Exception.Message)"
    }

    $requiredFields = @(
        "bundle_profile",
        "bundle_status",
        "merged_file_count",
        "scope_manifest_sha256",
        "manifest_sha256",
        "bundle_root_sha256",
        "bundle_file_sha256"
    )

    foreach ($field in $requiredFields) {
        $prop = $obj.PSObject.Properties[$field]
        if ($null -eq $prop -or $null -eq $prop.Value -or [string]::IsNullOrWhiteSpace([string]$prop.Value)) {
            throw "Manifest required field missing/empty: $field ; file=$ManifestPath"
        }
    }

    return [PSCustomObject]@{
        Profile             = [string]$obj.bundle_profile
        Status              = [string]$obj.bundle_status
        FileCount           = [int]$obj.merged_file_count
        ScopeSha256         = ([string]$obj.scope_manifest_sha256).ToLowerInvariant()
        ManifestSha256      = ([string]$obj.manifest_sha256).ToLowerInvariant()
        BundleRootSha256    = ([string]$obj.bundle_root_sha256).ToLowerInvariant()
        BundleFileSha256    = ([string]$obj.bundle_file_sha256).ToLowerInvariant()
        StrictMode          = $obj.strict_mode
        ManifestPath        = $ManifestPath
    }
}

function Assert-ManifestIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Identity,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedProfile,

        [Parameter(Mandatory = $true)]
        [string]$BundlePath
    )

    if ($Identity.Profile -ne $ExpectedProfile) {
        throw "Manifest profile mismatch: expected=$ExpectedProfile actual=$($Identity.Profile)"
    }

    if ($Identity.Status -ne "COMPLETE") {
        throw "Manifest bundle_status is not COMPLETE for profile $ExpectedProfile: $($Identity.Status)"
    }

    if ($Identity.StrictMode -ne $true) {
        throw "Manifest strict_mode is not true for profile $ExpectedProfile"
    }

    $actualBundleSha = (Get-FileHash -LiteralPath $BundlePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualBundleSha -ne $Identity.BundleFileSha256) {
        throw (
            "Bundle SHA256 does not match sidecar for profile ${ExpectedProfile}: " +
            "bundle=$actualBundleSha sidecar=$($Identity.BundleFileSha256)"
        )
    }
}

function Get-ChangeState {
    param(
        [object]$PreviousIdentity,
        [object]$CurrentIdentity
    )

    if ($null -eq $PreviousIdentity) {
        return "NO_PREVIOUS"
    }

    if ($PreviousIdentity.ManifestSha256 -eq $CurrentIdentity.ManifestSha256) {
        return "FALSE"
    }

    return "TRUE"
}

try {
    Write-Section "QCFP-MTF One-Click Review Bundle Builder"

    # -------------------------------------------------------------------------
    # 0. Identity hardening
    # -------------------------------------------------------------------------
    $ProjectRoot = Normalize-PathForCompare -Path $ProjectRoot
    $ExpectedProjectRootNormalized = Normalize-PathForCompare -Path $ExpectedProjectRoot

    if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
        throw "ProjectRoot does not exist: $ProjectRoot"
    }

    if (-not (Test-PathEqual -Left $ProjectRoot -Right $ExpectedProjectRootNormalized)) {
        throw (
            "PROJECT_ROOT_MISMATCH: wrapper ProjectRoot does not match the frozen builder root. " +
            "wrapper=$ProjectRoot ; expected=$ExpectedProjectRootNormalized"
        )
    }

    Write-Host "[PASS] ProjectRoot hard binding"
    Write-Host "       Wrapper : $ProjectRoot"
    Write-Host "       Expected: $ExpectedProjectRootNormalized"

    Set-Location -LiteralPath $ProjectRoot

    $MergerPath = Join-Path $ProjectRoot $MergerScript
    $MergerPath = [System.IO.Path]::GetFullPath($MergerPath)
    Assert-FileExists -Path $MergerPath -Description "Merger script"

    # Frozen merger SHA must be verified BEFORE any build is performed.
    $ActualMergerSha256 = (Get-FileHash -LiteralPath $MergerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualMergerSha256 -ne $ExpectedMergerSha256) {
        throw (
            "FROZEN_MERGER_SHA256_MISMATCH: " +
            "expected=$ExpectedMergerSha256 actual=$ActualMergerSha256 file=$MergerPath"
        )
    }

    Write-Host "[PASS] Frozen merger SHA256"
    Write-Host "       $ActualMergerSha256"

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

    # Capture previous source identities BEFORE the build overwrites manifests.
    # Previous evidence is only used for source-change comparison. In normal review
    # mode, a corrupt previous sidecar should not prevent regeneration; in
    # -RequireSourceChange mode it must fail because change cannot be proven.
    $PreviousCodeIdentity = $null
    $PreviousGovIdentity = $null

    try {
        $PreviousCodeIdentity = Get-ManifestIdentity -ManifestPath $CodeManifest -AllowMissing
    }
    catch {
        if ($RequireSourceChange) { throw }
        Write-Host "[WARN] Previous code-review manifest is unreadable; source-change comparison will be unavailable." -ForegroundColor Yellow
        Write-Host "       $($_.Exception.Message)"
        $PreviousCodeIdentity = $null
    }

    try {
        $PreviousGovIdentity = Get-ManifestIdentity -ManifestPath $GovManifest -AllowMissing
    }
    catch {
        if ($RequireSourceChange) { throw }
        Write-Host "[WARN] Previous governance-review manifest is unreadable; source-change comparison will be unavailable." -ForegroundColor Yellow
        Write-Host "       $($_.Exception.Message)"
        $PreviousGovIdentity = $null
    }

    # -------------------------------------------------------------------------
    # 1. Build code-review
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # 2. Verify code-review
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # 3. Build governance-review
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # 4. Verify governance-review
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Post-build sidecar identity checks
    # -------------------------------------------------------------------------
    $CurrentCodeIdentity = Get-ManifestIdentity -ManifestPath $CodeManifest
    $CurrentGovIdentity = Get-ManifestIdentity -ManifestPath $GovManifest

    Assert-ManifestIdentity `
        -Identity $CurrentCodeIdentity `
        -ExpectedProfile "code-review" `
        -BundlePath $CodeBundle

    Assert-ManifestIdentity `
        -Identity $CurrentGovIdentity `
        -ExpectedProfile "governance-review" `
        -BundlePath $GovBundle

    $CodeSourceChanged = Get-ChangeState `
        -PreviousIdentity $PreviousCodeIdentity `
        -CurrentIdentity $CurrentCodeIdentity

    $GovSourceChanged = Get-ChangeState `
        -PreviousIdentity $PreviousGovIdentity `
        -CurrentIdentity $CurrentGovIdentity

    $AnySourceChanged = (
        $CodeSourceChanged -eq "TRUE" -or
        $GovSourceChanged -eq "TRUE"
    )

    $PreviousIdentityAvailable = (
        $null -ne $PreviousCodeIdentity -or
        $null -ne $PreviousGovIdentity
    )

    $PreviousIdentityComplete = (
        $null -ne $PreviousCodeIdentity -and
        $null -ne $PreviousGovIdentity
    )

    if ($RequireSourceChange) {
        if (-not $PreviousIdentityComplete) {
            throw (
                "RequireSourceChange was specified, but both previous review manifests are not available. " +
                "Cannot prove source change against a complete previous build."
            )
        }

        if (-not $AnySourceChanged) {
            throw (
                "SOURCE_MANIFEST_UNCHANGED: RequireSourceChange was specified, but both " +
                "code-review and governance-review source manifests are unchanged. " +
                "Verify that the patch was saved to the actual project tree."
            )
        }
    }
    elseif ($PreviousIdentityAvailable -and -not $AnySourceChanged) {
        Write-Host ""
        Write-Host "[WARN] Source manifests are unchanged from the previous build." -ForegroundColor Yellow
        Write-Host "       If this build was expected to contain a patch, verify that the patch"
        Write-Host "       was saved to the actual project tree before requesting acceptance."
    }

    # -------------------------------------------------------------------------
    # Final evidence summary
    # -------------------------------------------------------------------------
    Write-Section "FINAL RESULT"

    $MergerSha = $ActualMergerSha256
    $CodeSha = (Get-FileHash -LiteralPath $CodeBundle -Algorithm SHA256).Hash.ToLowerInvariant()
    $GovSha = (Get-FileHash -LiteralPath $GovBundle -Algorithm SHA256).Hash.ToLowerInvariant()

    $PreviousCodeManifestSha = if ($null -eq $PreviousCodeIdentity) {
        "NONE"
    }
    else {
        $PreviousCodeIdentity.ManifestSha256
    }

    $PreviousGovManifestSha = if ($null -eq $PreviousGovIdentity) {
        "NONE"
    }
    else {
        $PreviousGovIdentity.ManifestSha256
    }

    $SummaryPath = Join-Path $MergedDir "review_bundle_build_summary.txt"

    $summary = @"
QCFP-MTF REVIEW BUNDLE BUILD SUMMARY
====================================

STATUS:
PASS

SOURCE EVIDENCE ONLY:
TRUE

PROJECT ROOT BINDING:
Wrapper Root : $ProjectRoot
Expected Root: $ExpectedProjectRootNormalized
Verdict      : PASS

FROZEN MERGER:
Path            : $MergerPath
Expected SHA256 : $ExpectedMergerSha256
Actual SHA256   : $MergerSha
Identity        : PASS

CODE REVIEW:
Bundle          : $CodeBundle
Manifest        : $CodeManifest
Verify          : $CodeVerifyLog
Files           : $($CurrentCodeIdentity.FileCount)
Bundle SHA256   : $CodeSha
Manifest SHA256 : $($CurrentCodeIdentity.ManifestSha256)
Scope SHA256    : $($CurrentCodeIdentity.ScopeSha256)
Root SHA256     : $($CurrentCodeIdentity.BundleRootSha256)
Verdict         : BUNDLE_VERIFIED

GOVERNANCE REVIEW:
Bundle          : $GovBundle
Manifest        : $GovManifest
Verify          : $GovVerifyLog
Files           : $($CurrentGovIdentity.FileCount)
Bundle SHA256   : $GovSha
Manifest SHA256 : $($CurrentGovIdentity.ManifestSha256)
Scope SHA256    : $($CurrentGovIdentity.ScopeSha256)
Root SHA256     : $($CurrentGovIdentity.BundleRootSha256)
Verdict         : BUNDLE_VERIFIED

SOURCE CHANGE SINCE PREVIOUS BUILD:
Previous Code Manifest       : $PreviousCodeManifestSha
Current Code Manifest        : $($CurrentCodeIdentity.ManifestSha256)
Code Source Changed          : $CodeSourceChanged
Previous Governance Manifest : $PreviousGovManifestSha
Current Governance Manifest  : $($CurrentGovIdentity.ManifestSha256)
Governance Source Changed    : $GovSourceChanged
Any Source Changed           : $AnySourceChanged
Require Source Change        : $($RequireSourceChange.IsPresent)

READY FOR SOURCE REVIEW:
TRUE

NOTE:
This summary proves source-bundle identity/integrity only.
It does NOT prove Phase3 regression, Phase3 acceptance, baseline promotion,
or final freeze readiness.
"@

    $summary | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

    Write-Host "[PASS] code-review       : BUNDLE_VERIFIED"
    Write-Host "[PASS] governance-review : BUNDLE_VERIFIED"
    Write-Host "[PASS] frozen merger     : SHA256 MATCH"
    Write-Host "[PASS] project root      : HARD BOUND"
    Write-Host ""
    Write-Host "Source change:"
    Write-Host "  code-review       : $CodeSourceChanged"
    Write-Host "  governance-review : $GovSourceChanged"
    Write-Host "  any source changed: $AnySourceChanged"
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
    Write-Host "READY FOR SOURCE REVIEW: TRUE"
    exit 0
}
catch {
    Write-Host ""
    Write-Host ("=" * 88)
    Write-Host "QCFP-MTF REVIEW BUNDLE BUILD FAILED"
    Write-Host ("=" * 88)
    Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "No formal source review should use the output until this error is resolved."
    exit 1
}
