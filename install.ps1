# ================================================
#   PS99 ClanWar Bot - Install & Update Script
#   Einfach in PowerShell ausführen:
#   .\install.ps1
# ================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   PS99 ClanWar Bot - Auto Installer   " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Pfade ──────────────────────────────────────────────────────────
# Wo liegt dein Bot-Ordner (GitHub Repo)?
$BOT_DIR = "C:\Users\Notix\Desktop\ps99-cwbot"

# Wo liegt die entpackte ZIP? (Ordner der nach dem Entpacken entsteht)
# Das Script sucht automatisch nach einem "cwbot" Ordner auf dem Desktop
$DESKTOP   = [Environment]::GetFolderPath("Desktop")
$ZIP_SRC   = "$DESKTOP\cwbot"

# ── Prüfungen ──────────────────────────────────────────────────────
if (-not (Test-Path $ZIP_SRC)) {
    Write-Host "❌ Ordner '$ZIP_SRC' nicht gefunden!" -ForegroundColor Red
    Write-Host ""
    Write-Host "➡️  Bitte erst die ZIP auf dem Desktop entpacken." -ForegroundColor Yellow
    Write-Host "   Es muss ein Ordner namens 'cwbot' auf dem Desktop entstehen." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Enter drücken zum Beenden"
    exit 1
}

if (-not (Test-Path $BOT_DIR)) {
    Write-Host "❌ Bot-Ordner '$BOT_DIR' nicht gefunden!" -ForegroundColor Red
    Write-Host "   Bitte passe den Pfad in install.ps1 Zeile 15 an." -ForegroundColor Yellow
    Read-Host "Enter drücken zum Beenden"
    exit 1
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git nicht gefunden! Bitte installiere Git von https://git-scm.com" -ForegroundColor Red
    Read-Host "Enter drücken zum Beenden"
    exit 1
}

# ── Dateien kopieren & altes löschen ──────────────────────────────
Write-Host "📁 Kopiere neue Dateien nach: $BOT_DIR" -ForegroundColor Yellow
Write-Host ""

# Alle Dateien aus der ZIP-Quelle holen
$newFiles = Get-ChildItem -Path $ZIP_SRC -Recurse -File | ForEach-Object {
    $_.FullName.Replace($ZIP_SRC, "").TrimStart("\")
}

# Alle aktuellen Dateien im Bot-Ordner holen (außer .git und data)
$oldFiles = Get-ChildItem -Path $BOT_DIR -Recurse -File | Where-Object {
    $_.FullName -notlike "*\.git\*" -and
    $_.FullName -notlike "*\data\*" -and
    $_.FullName -notlike "*\__pycache__\*" -and
    $_.Name -ne ".env"
} | ForEach-Object {
    $_.FullName.Replace($BOT_DIR, "").TrimStart("\")
}

# Dateien löschen die in neu nicht mehr vorhanden sind
$toDelete = $oldFiles | Where-Object { $_ -notin $newFiles }
if ($toDelete.Count -gt 0) {
    Write-Host "🗑️  Lösche veraltete Dateien:" -ForegroundColor Red
    foreach ($f in $toDelete) {
        $fullPath = Join-Path $BOT_DIR $f
        Remove-Item $fullPath -Force -ErrorAction SilentlyContinue
        Write-Host "   ❌ $f" -ForegroundColor Red
    }
    Write-Host ""
}

# Neue Dateien kopieren (überschreiben)
Write-Host "✅ Kopiere neue/geänderte Dateien:" -ForegroundColor Green
foreach ($f in $newFiles) {
    $src  = Join-Path $ZIP_SRC $f
    $dest = Join-Path $BOT_DIR $f

    # Zielordner erstellen falls nötig
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    Copy-Item $src $dest -Force
    Write-Host "   ✅ $f" -ForegroundColor Green
}

Write-Host ""

# ── .env prüfen ────────────────────────────────────────────────────
$envFile = Join-Path $BOT_DIR ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "⚠️  Keine .env Datei gefunden!" -ForegroundColor Yellow
    Write-Host "   Kopiere .env.example als .env..." -ForegroundColor Yellow
    $envExample = Join-Path $BOT_DIR ".env.example"
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "   ➡️  Bitte $envFile mit deinen Tokens befüllen!" -ForegroundColor Yellow
    }
    Write-Host ""
}

# ── Git: push ──────────────────────────────────────────────────────
Set-Location $BOT_DIR

Write-Host "🔄 Pushe zu GitHub..." -ForegroundColor Yellow
Write-Host ""

git add .

$timestamp = Get-Date -Format "dd.MM.yyyy HH:mm"
$commitMsg = "update: $timestamp"
git commit -m $commitMsg

git push

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "   ✅ Alles erledigt!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "🚀 Render deployed jetzt automatisch." -ForegroundColor Cyan
    Write-Host "⏳ Warte ~2 Minuten dann teste !cb ZYXE" -ForegroundColor Cyan
    Write-Host "📊 Status: https://dashboard.render.com" -ForegroundColor Cyan
} else {
    Write-Host "❌ Push fehlgeschlagen! Fehler siehe oben." -ForegroundColor Red
}

Write-Host ""

# ── ZIP-Quelle aufräumen ───────────────────────────────────────────
$cleanup = Read-Host "🗑️  Entpackten 'cwbot' Ordner vom Desktop löschen? (j/n)"
if ($cleanup -eq "j" -or $cleanup -eq "J") {
    Remove-Item $ZIP_SRC -Recurse -Force
    Write-Host "✅ Aufgeräumt!" -ForegroundColor Green
}

Write-Host ""
Read-Host "Enter drücken zum Beenden"
