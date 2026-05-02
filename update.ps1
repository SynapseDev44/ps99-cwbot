# PS99 ClanWar Bot - Auto Update Script
# Einfach Doppelklick auf diese Datei!

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PS99 ClanWar Bot - Auto Updater" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Bot-Ordner finden (script liegt im gleichen Ordner)
$BOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BOT_DIR

Write-Host "📁 Bot-Ordner: $BOT_DIR" -ForegroundColor Yellow
Write-Host ""

# Prüfen ob git installiert ist
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git nicht gefunden! Bitte installiere Git von https://git-scm.com" -ForegroundColor Red
    Read-Host "Enter drücken zum Beenden"
    exit
}

# Git Status anzeigen
Write-Host "📋 Geänderte Dateien:" -ForegroundColor Yellow
git status --short

Write-Host ""
Write-Host "⬆️  Pushe alle Änderungen zu GitHub..." -ForegroundColor Yellow

# Alle Dateien adden
git add .

# Commit mit Zeitstempel
$timestamp = Get-Date -Format "dd.MM.yyyy HH:mm"
git commit -m "update: $timestamp"

# Pushen
git push

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Erfolgreich gepusht!" -ForegroundColor Green
    Write-Host "🚀 Render deployed automatisch in ~2 Minuten." -ForegroundColor Green
    Write-Host "👉 Prüfe den Status auf: https://dashboard.render.com" -ForegroundColor Cyan
} else {
    Write-Host "❌ Push fehlgeschlagen! Fehler siehe oben." -ForegroundColor Red
}

Write-Host ""
Read-Host "Enter drücken zum Beenden"
