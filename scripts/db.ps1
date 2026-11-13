# Project-local PostgreSQL (port 5433). Usage:  .\scripts\db.ps1 start | stop | status
param([string]$cmd = "status")
$pg = "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe"
$data = Join-Path $PSScriptRoot "..\data\pg\cluster"
$log = Join-Path $PSScriptRoot "..\data\pg\server.log"
switch ($cmd) {
  "start"  { & $pg -D $data -o "-p 5433 -c listen_addresses=localhost" -l $log start }
  "stop"   { & $pg -D $data stop }
  default  { & $pg -D $data status }
}
