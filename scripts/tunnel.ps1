# Forwards localhost:11435 -> Ollama (port 11434) on the GPU server. Keep this window open.
# The server is the SSH alias in GPU_SSH_HOST (backend/.env), e.g. an entry in ~/.ssh/config.
$envFile = Join-Path $PSScriptRoot "..\backend\.env"
$gpuHost = $env:GPU_SSH_HOST
if (-not $gpuHost -and (Test-Path $envFile)) {
  $line = Select-String -Path $envFile -Pattern '^\s*GPU_SSH_HOST\s*=\s*(.+)$' | Select-Object -First 1
  if ($line) { $gpuHost = $line.Matches[0].Groups[1].Value.Trim() }
}
if (-not $gpuHost) { Write-Error "Set GPU_SSH_HOST in backend/.env (an SSH host alias for the GPU server)."; exit 1 }

Write-Host "GPU tunnel: localhost:11435 -> $gpuHost:11434 (keep open)"
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 11435:localhost:11434 $gpuHost
