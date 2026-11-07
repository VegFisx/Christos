[CmdletBinding()]
param(
    [string[]]$Files = @(
        "D:\ProgramData\DSHNS\chemreact-staging\reports\desktop-build\dist-v090\Christos\Christos.exe",
        "D:\ProgramData\DSHNS\chemreact-staging\reports\desktop-build\release-v090\Christos-Setup-0.9.0-beta.exe",
        "D:\ProgramData\DSHNS\chemreact-staging\reports\desktop-build\demo-dist-fixed-v090\Christos-Demo\Christos-Demo.exe"
    ),
    [string]$CertificateThumbprint = "",
    [string]$PfxPath = "",
    [string]$PfxPassword = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Find-SignTool {
    $candidates = @(
        (Get-Command signtool.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
    )
    $roots = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "$env:ProgramFiles\Windows Kits\10\bin"
    )
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $candidates += Get-ChildItem $root -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
                Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
        }
    }
    $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

if (-not $CertificateThumbprint -and -not $PfxPath) {
    throw "Provide -CertificateThumbprint or -PfxPath. This script does not create or install certificates."
}
if ($PfxPath -and -not (Test-Path -LiteralPath $PfxPath)) {
    throw "PFX file not found: $PfxPath"
}
$signtool = Find-SignTool
if (-not $signtool -and -not $DryRun) {
    throw "signtool.exe not found. Install Windows SDK Signing Tools."
}

$common = @("sign", "/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256")
if ($PfxPath) {
    $common += @("/f", $PfxPath)
    if ($PfxPassword) { $common += @("/p", $PfxPassword) }
} else {
    $common += @("/sha1", $CertificateThumbprint)
}

foreach ($file in $Files) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "File not found: $file"
    }
    $signArgs = $common + @($file)
    if ($DryRun) {
        "[DRY-RUN] $signtool $($signArgs -join ' ')"
        continue
    }
    & $signtool @signArgs
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $file (exit $LASTEXITCODE)" }
    & $signtool verify /pa /v $file
    if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $file" }
    Get-AuthenticodeSignature -LiteralPath $file |
        Select-Object Path,Status,StatusMessage,SignerCertificate |
        Format-List
}

