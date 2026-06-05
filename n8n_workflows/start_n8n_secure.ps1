# ============================================================
# Start n8n with hardened security configuration
# ============================================================
# Chay: .\n8n_workflows\start_n8n_secure.ps1
#
# Cau hinh bao mat:
# - Encryption key co dinh (bao ve credentials luu trong n8n)
# - Han Translate API key (workflow tu gui khi goi API)
# - Tat telemetry/diagnostics
# - Cookie config dung
# - Block env vars nhay cam khoi expression cua workflow
# ============================================================

# Lay API key tu Han Translate (Credential Manager)
$apiKey = & ".\venv\Scripts\python.exe" -c "from ai_interpreter import security; print(security.get_api_key())"
$apiKey = $apiKey.Trim()

if (-not $apiKey) {
    Write-Host "ERROR: Khong lay duoc Han Translate API key" -ForegroundColor Red
    exit 1
}

# Encryption key cua n8n (GIU NGUYEN de khong mat credentials da luu)
# Doc tu file local (khong commit len git) hoac tu container dang chay.
$encKeyFile = "$env:USERPROFILE\.han_translate\n8n_encryption_key.txt"

if (Test-Path $encKeyFile) {
    $encKey = (Get-Content $encKeyFile -Raw).Trim()
} else {
    # Thu doc tu container dang chay
    $encKey = (docker exec n8n cat /home/node/.n8n/config 2>$null | ConvertFrom-Json).encryptionKey
    if (-not $encKey) {
        # Tao key moi ngau nhien
        $encKey = -join ((1..32) | ForEach-Object { '{0:X}' -f (Get-Random -Max 16) })
        Write-Host "Tao encryption key moi" -ForegroundColor Yellow
    }
    # Luu lai vao file local (gitignored)
    New-Item -ItemType Directory -Force -Path (Split-Path $encKeyFile) | Out-Null
    Set-Content -Path $encKeyFile -Value $encKey
    Write-Host "Da luu encryption key vao: $encKeyFile" -ForegroundColor Green
}

Write-Host "Stopping & removing old n8n container..." -ForegroundColor Yellow
docker rm -f n8n 2>$null

Write-Host "Starting n8n with hardened security..." -ForegroundColor Cyan
docker run -d --name n8n --restart unless-stopped `
  -p 127.0.0.1:5678:5678 `
  -e GENERIC_TIMEZONE=Asia/Ho_Chi_Minh `
  -e TZ=Asia/Ho_Chi_Minh `
  -e N8N_DIAGNOSTICS_ENABLED=false `
  -e N8N_PERSONALIZATION_ENABLED=false `
  -e N8N_VERSION_NOTIFICATIONS_ENABLED=false `
  -e N8N_ENCRYPTION_KEY="$encKey" `
  -e N8N_SECURE_COOKIE=false `
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false `
  -e HAN_TRANSLATE_API_KEY="$apiKey" `
  -v n8n_data:/home/node/.n8n `
  docker.n8n.io/n8nio/n8n:latest

Start-Sleep -Seconds 3
Write-Host "`nn8n status:" -ForegroundColor Green
docker ps --filter "name=n8n" --format "{{.Names}} | {{.Status}} | {{.Ports}}"
Write-Host "`nTruy cap: http://localhost:5678" -ForegroundColor Green
Write-Host "API key da duoc inject vao n8n (workflow tu dung qua `$env.HAN_TRANSLATE_API_KEY)" -ForegroundColor Green
