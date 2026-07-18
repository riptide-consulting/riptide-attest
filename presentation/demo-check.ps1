# demo-check.ps1: one command to get demo-ready (Riptide Attest).
#
# Rebuilds the deck and technical documentation from source, runs the
# quality gates, the 234-test offline suite, and the self-verifying demo.
# Any failure stops loudly; a green run ends with the deck path.
#
# Run from anywhere:  powershell -File presentation\demo-check.ps1

$ErrorActionPreference = "Stop"
$pres = $PSScriptRoot
$repo = Split-Path $pres -Parent
$py = Join-Path $repo ".venv\Scripts\python.exe"

function Step($name, $script) {
    Write-Host ""
    Write-Host "== $name" -ForegroundColor Cyan
    & $script
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $name (exit $LASTEXITCODE). Not demo-ready." -ForegroundColor Red
        exit 1
    }
}

Step "Rebuild diagrams" {
    Set-Location $pres; & $py diagrams\diagrams.py
}
Step "Rebuild the deck" {
    Set-Location $pres; node build\build_deck.js
}
Step "Rebuild the technical documentation" {
    Set-Location $pres; node build\build_techdoc.js
}
Step "Contrast gate (expect failures: 0)" {
    Set-Location $pres; & $py qa\contrast_gate.py out\Riptide-Attest-Master-Deck.pptx
}
Step "Layout gate (expect geometry OK, image aspect OK, text fit OK)" {
    Set-Location $pres; & $py qa\layout_gate.py out\Riptide-Attest-Master-Deck.pptx
}
Step "Offline test suite (expect 234 passed)" {
    Set-Location $repo
    $out = & $py -m pytest tests -q 2>&1 | Select-Object -Last 1
    Write-Host $out
    if ($out -notmatch "234 passed") {
        Write-Host "Test count is not 234 passed. Investigate before demoing." -ForegroundColor Red
        exit 1
    }
    $global:LASTEXITCODE = 0
}
Step "Self-verifying demo (expect ALL ASSERTIONS HELD, exit 0)" {
    Set-Location $repo; & $py run_demo.py
}

Write-Host ""
Write-Host "== Demo posture" -ForegroundColor Cyan
if ($env:ATTEST_PUBLISH_APPROVED) {
    Write-Host "WARNING: ATTEST_PUBLISH_APPROVED is SET. The blocked publish IS the demo." -ForegroundColor Yellow
    Write-Host "Unset it for the room:  Remove-Item Env:ATTEST_PUBLISH_APPROVED" -ForegroundColor Yellow
} else {
    Write-Host "ATTEST_PUBLISH_APPROVED is not set. Correct: the refusal is the product." -ForegroundColor Green
}

Write-Host ""
Write-Host "DEMO-READY." -ForegroundColor Green
Write-Host "Deck: $(Join-Path $pres 'out\Riptide-Attest-Master-Deck.pptx')"
Write-Host "Doc:  $(Join-Path $pres 'out\Riptide-Attest-Technical-Documentation.docx')"
