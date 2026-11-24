# Puxa os backups do Sistema de Estoque da VM para este PC (copia fora da VM).
# Agendado pelo Agendador de Tarefas do Windows (ver DEPLOY-VM.md, secao 7.1).
# - Copia so os dumps que ainda nao existem aqui, conferindo o tamanho.
# - Mantem -ManterDias dias neste PC (padrao 60).
# - Registra tudo em <Destino>\puxar-backup.log
param(
    [Parameter(Mandatory = $true)][string]$Vm,        # ex.: estoque-prod@10.11.66.50
    [Parameter(Mandatory = $true)][string]$Destino,   # pasta neste PC
    [string]$PastaRemota = "/var/backups/estoque",
    [int]$ManterDias = 60
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$log = Join-Path $Destino "puxar-backup.log"
function Log([string]$m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content -Path $log -Encoding UTF8 }

$sshOpts = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=15")
try {
    # Lista "tamanho nome" dos dumps prontos na VM
    $lista = & ssh @sshOpts $Vm "cd '$PastaRemota' && stat -c '%s %n' estoque-*.dump"
    if ($LASTEXITCODE -ne 0) { throw "ssh falhou (codigo $LASTEXITCODE)" }

    $novos = 0
    foreach ($linha in $lista) {
        $partes = $linha.Trim() -split " ", 2
        if ($partes.Count -ne 2) { continue }
        $tamanho = [int64]$partes[0]
        $nome = $partes[1]
        $local = Join-Path $Destino $nome
        if ((Test-Path $local) -and ((Get-Item $local).Length -eq $tamanho)) { continue }

        $tmp = "$local.part"
        & scp -p -q @sshOpts "${Vm}:$PastaRemota/$nome" $tmp
        if ($LASTEXITCODE -ne 0) { Remove-Item $tmp -ErrorAction SilentlyContinue; throw "scp falhou em $nome" }
        if ((Get-Item $tmp).Length -ne $tamanho) { Remove-Item $tmp; throw "tamanho diferente em $nome" }
        Move-Item -Force $tmp $local
        $novos++
    }

    $limite = (Get-Date).AddDays(-$ManterDias)
    Get-ChildItem -Path $Destino -Filter "estoque-*.dump" |
        Where-Object { $_.LastWriteTime -lt $limite } | Remove-Item

    $total = (Get-ChildItem -Path $Destino -Filter "estoque-*.dump").Count
    Log "ok: $novos novo(s), $total no PC"
}
catch {
    Log "ERRO: $_"
    exit 1
}
