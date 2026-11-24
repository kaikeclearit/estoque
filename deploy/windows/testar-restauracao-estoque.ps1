# Teste de restauracao usando a COPIA DO PC (valida VM -> PC -> restauracao).
# Envia o ultimo dump desta pasta para a VM e roda deploy/estoque-teste-restore.sh
# (banco temporario; producao nao e alterada). Ver DEPLOY-VM.md, secao 7.2.
param(
    [string]$Vm = "estoque-vm",
    [string]$Origem = "C:\Users\KaikeMaciel\Automa$([char]0x00E7)$([char]0x00F5)es\backup-estoque",
    [string]$PastaProjetoVm = "~/estoque"
)
$ErrorActionPreference = "Stop"
$ultimo = Get-ChildItem -Path $Origem -Filter "estoque-*.dump" | Sort-Object Name | Select-Object -Last 1
if (-not $ultimo) { Write-Error "Nenhum dump em $Origem"; exit 1 }
Write-Host "Usando a copia do PC: $($ultimo.Name)"

$remoto = "/tmp/$($ultimo.Name)"
& scp -q -o BatchMode=yes $ultimo.FullName "${Vm}:$remoto"
if ($LASTEXITCODE -ne 0) { Write-Error "scp falhou"; exit 1 }

& ssh -o BatchMode=yes $Vm "sh $PastaProjetoVm/deploy/estoque-teste-restore.sh $remoto --apagar-dump"
$rc = $LASTEXITCODE
if ($rc -eq 0) { Write-Host "Restauracao OK" -ForegroundColor Green } else { Write-Host "FALHOU (codigo $rc)" -ForegroundColor Red }
exit $rc
