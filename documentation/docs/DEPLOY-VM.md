# Deploy em VM (Nutanix AHV) com Docker Compose

Sistema de Estoque ClearIT rodando numa VM única, no IP **10.11.10.10**
(o mesmo da antiga VM no VMware). App (Gunicorn + WhiteNoise) e Postgres em
containers; acesso em `http://10.11.10.10`.

> Produção roda **só na VM** com Docker Compose. Os manifests da pasta `nginx/`
> (Kubernetes) não estão em uso.

---

## 0. Antes de começar — dados da VM antiga (VMware)

O banco de produção estava no disco da VM antiga. **Recupere o dump antes de
qualquer outra coisa.**

- **Se a VM antiga ainda liga** (mesmo com o sistema quebrado):
  ```bash
  docker ps                                   # descubra o nome do container do Postgres
  docker exec <container_db> pg_dump -U <usuario> -Fc <banco> > estoque.dump
  ```
  Copie o `estoque.dump` para fora (ex.: `scp`).
- **Se não liga:** anexe o disco (VMDK) dela a outra VM para ler o volume do
  Docker (`/var/lib/docker/volumes/...postgres_data`), ou migre a VM inteira
  para o Nutanix com o **Nutanix Move** e faça o dump lá.

Depois de ter o dump, **desligue a VM antiga** (ou desconecte a placa de rede no
vSphere): o IP 10.11.10.10 não pode responder em duas máquinas ao mesmo tempo.
Confira: `ping 10.11.10.10` não deve responder.

---

## 1. Criar a VM no Prism (Nutanix AHV)

| Item | Recomendado |
|---|---|
| SO | Ubuntu Server 24.04 LTS (ou Rocky/RHEL 9) |
| vCPU / RAM | 2 vCPU / 4 GB (mínimo 2 GB) |
| Disco | 40 GB |
| Rede | **Mesma VLAN/sub-rede da 10.11.10.10** |
| IP | **Estático 10.11.10.10** (máscara, gateway e DNS da rede) |

No Ubuntu, IP fixo via netplan (`/etc/netplan/50-cloud-init.yaml`), exemplo:
```yaml
network:
  version: 2
  ethernets:
    ens3:
      dhcp4: false
      addresses: [10.11.10.10/24]        # ajuste a máscara
      routes: [{to: default, via: 10.11.10.1}]   # ajuste o gateway
      nameservers: {addresses: [10.11.10.2]}     # ajuste o DNS
```
`sudo netplan apply` e confirme com `ip a`.

---

## 2. Instalar o Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER     # saia e entre de novo na sessão
docker compose version
```

Firewall da VM (se usar ufw): liberar só SSH e HTTP.
```bash
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw enable
```

---

## 3. Colocar o sistema na VM

```bash
sudo mkdir -p /opt/estoque && sudo chown $USER /opt/estoque
cd /opt/estoque
git clone git@github.com:kaikeclearit/estoque.git .
cp env.vm.example .env
nano .env        # preencha DJANGO_SECRET_KEY, DATABASE_PASSWORD etc.
chmod 600 .env
```

---

## 4. Restaurar o banco da VM antiga

Suba **só o banco** e restaure o dump antes de subir o app:
```bash
docker compose up -d db
docker compose cp estoque.dump db:/tmp/estoque.dump
docker compose exec db sh -c 'pg_restore --no-owner --role="$POSTGRES_USER" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/estoque.dump'
```
Confira as migrations que vieram da produção:
```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "select name from django_migrations where app='"'"'core'"'"' order by id;"'
```
A última deve ser `0006_stockout_cancelled_at_...`. **Se aparecer qualquer
0007+ com outro nome, pare** — as migrations do repositório precisam ser
ajustadas antes.

> Banco novo (sem dados antigos)? Pule esta etapa; o passo 5 cria tudo.

---

## 5. Subir o sistema

```bash
docker compose up -d --build
docker compose logs migrate        # deve terminar sem erro (aplica 0007 a 0013)
docker compose ps                  # web e db "healthy/running"; migrate "exited (0)"
curl -I http://10.11.10.10/login/  # HTTP 200
```

Primeiro acesso / superusuário:
```bash
docker compose exec web python manage.py createsuperuser
```
Depois, pela tela **Usuários**, atribua os perfis (Admin, Gestor, Dev,
Pós-vendas, Pré-vendas). Quem estava no grupo antigo "Gestores" já vira
**Gestor** automaticamente; os demais ficam só com leitura até receber perfil.

---

## 6. Subida automática (nunca mais dar `up` na mão)

Três camadas, cada uma cobre uma falha diferente:

| Camada | Cobre |
|---|---|
| `restart: always` no compose (web e db) | processo/container caiu → Docker reinicia na hora |
| `estoque.service` (systemd) | VM reiniciou, ou alguém rodou `docker compose down` antes do reboot |
| `estoque-watchdog.timer` (a cada 2 min) | container parado/removido, ou web travado (`unhealthy`) |

Instalação (uma vez; se o projeto **não** estiver em `/opt/estoque`, ajuste
`WorkingDirectory`, `ESTOQUE_DIR` e o caminho do script nos arquivos de `deploy/`):
```bash
sudo systemctl enable docker containerd
sudo cp /opt/estoque/deploy/estoque.service \
        /opt/estoque/deploy/estoque-watchdog.service \
        /opt/estoque/deploy/estoque-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now estoque.service estoque-watchdog.timer
```

Teste (faça agora, não no dia do problema):
```bash
docker compose kill web; sleep 5; docker compose ps          # web volta sozinho
docker compose down; sudo systemctl start estoque-watchdog.service; docker compose ps   # volta
sudo reboot        # depois: curl -I http://localhost/login/  -> 200, sem rodar nada
journalctl -u estoque-watchdog.service --since today          # histórico do vigia
```

No Nutanix, ligue também o **HA** do cluster para a VM: se o host físico cair,
a VM liga em outro host e as camadas acima sobem o sistema.

---

## 7. Backup diário

`deploy/estoque-backup.sh` roda todo dia às 02:00 (timer do systemd; se a VM
estava desligada nesse horário, roda assim que ligar):
- `pg_dump` validado com `pg_restore --list` (dump corrompido não é aceito);
- guarda em `/var/backups/estoque`, 30 dias;
- opcional: copia para uma pasta de outro servidor/NAS (`BACKUP_COPY_TO`).

Instalação (troca `/opt/estoque` pelo caminho real do projeto):
```bash
cd ~/estoque
D=$(pwd)
for f in estoque-backup.service estoque-backup.timer; do
  sed "s#/opt/estoque#$D#g" deploy/$f | sudo tee /etc/systemd/system/$f >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now estoque-backup.timer
sudo systemctl start estoque-backup.service      # primeiro backup agora
journalctl -u estoque-backup.service -n 5 --no-pager   # "backup: ok ..."
sudo ls -lh /var/backups/estoque
```
Acompanhar: `systemctl list-timers estoque-backup.timer` (próxima execução) e
`systemctl --failed` (aparece se algum backup falhar).

### 7.1 Cópia fora da VM (obrigatório)
Backup só dentro da VM não protege contra perda da VM/disco. Opções:
- **PC/servidor Windows puxando da VM** (solução provisória, abaixo);
- **ExaGrid/Veeam/Commvault:** incluir `/var/backups/estoque` no job da VM;
- **Pasta de rede montada** (NFS/SMB): `Environment=BACKUP_COPY_TO=/mnt/...`
  em `/etc/systemd/system/estoque-backup.service`;
- Snapshot/Protection Domain do Nutanix complementa, mas não substitui o dump.

#### PC Windows puxando os backups (provisório)
O PC busca os dumps quando está ligado (agendado diário e ao fazer logon),
copia só os que faltam e confere o tamanho. Se o PC ficar desligado alguns dias,
na próxima execução ele pega tudo que ficou para trás (a VM guarda 30 dias).

**1. Na VM** — deixar os dumps legíveis pelo usuário SSH:
```bash
sudo sed -i "s#^Environment=BACKUP_OWNER=.*#Environment=BACKUP_OWNER=$USER#" /etc/systemd/system/estoque-backup.service
sudo systemctl daemon-reload
sudo systemctl start estoque-backup.service
ls -l /var/backups/estoque        # dono = seu usuário
```

**2. No PC (PowerShell, sem admin)** — chave SSH sem senha só para isso:
```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\estoque_backup" -N '""' -C "backup-estoque-pc"
type "$env:USERPROFILE\.ssh\estoque_backup.pub" | ssh <usuario>@<IP_DA_VM> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
Add-Content "$env:USERPROFILE\.ssh\config" "`nHost estoque-vm`n  HostName <IP_DA_VM>`n  User <usuario>`n  IdentityFile ~/.ssh/estoque_backup`n"
ssh -o BatchMode=yes estoque-vm "ls /var/backups/estoque"   # deve listar sem pedir senha
```

**3. Testar o script e agendar:**
```powershell
$script  = "<caminho do repo>\deploy\windows\puxar-backup-estoque.ps1"
$destino = "<pasta de destino no PC>"
powershell -NoProfile -ExecutionPolicy Bypass -File $script -Vm estoque-vm -Destino $destino
Get-Content "$destino\puxar-backup.log" -Tail 3            # "ok: N novo(s)"

$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Vm estoque-vm -Destino `"$destino`""
$gatilhos = @(
  (New-ScheduledTaskTrigger -Daily -At 9am),
  (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME)
)
$cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable
Register-ScheduledTask -TaskName "Estoque - puxar backup" -Action $acao -Trigger $gatilhos -Settings $cfg
```
Conferir de vez em quando: `Get-Content "<destino>\puxar-backup.log" -Tail 5`.

> Os dumps têm dados do sistema: a pasta de destino não deve ser
> compartilhada nem ficar dentro de um repositório git (o `.gitignore` já ignora
> `*.dump` e `backups/` por segurança). Quando o ExaGrid/Veeam estiver
> disponível, desative a tarefa (`Disable-ScheduledTask "Estoque - puxar backup"`).

Guarde também uma cópia do `.env` em local seguro (cofre de senhas): sem a
`DJANGO_SECRET_KEY` e a senha do banco, restaurar fica mais trabalhoso.

### 7.2 Testar a restauração (agora e a cada 2–3 meses)
Restaura num banco temporário (`teste_restore`), compara a contagem de linhas de
todas as tabelas com a produção e apaga o temporário. Produção não é alterada.

**Pelo PC (recomendado — testa a cópia que está fora da VM):**
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\KaikeMaciel\Automações\estoque-prod\deploy\windows\testar-restauracao-estoque.ps1"
```

**Direto na VM (último backup da VM, ou um arquivo específico):**
```bash
cd ~/estoque
sh deploy/estoque-teste-restore.sh
sh deploy/estoque-teste-restore.sh /var/backups/estoque/estoque-<DATA>.dump
```
Resultado esperado: `restauração: ok`, mesmo número de tabelas, `TESTE OK`.
Diferenças de contagem são normais se o sistema foi usado depois do backup.

### 7.3 Restaurar de verdade (desastre)
```bash
sudo systemctl stop estoque-watchdog.timer   # senão o vigia religa o web no meio
docker compose stop web
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
sudo cat /var/backups/estoque/estoque-<DATA>.dump | docker compose exec -T db sh -c \
  'pg_restore --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose start web
sudo systemctl start estoque-watchdog.timer
```

---

## 8. Atualizar a versão

```bash
cd /opt/estoque
sudo systemctl start estoque-backup.service   # backup antes de atualizar
git pull
docker compose up -d --build      # o serviço migrate roda as migrations novas
```

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `Bad Request (400)` | Host/IP usado não está em `DJANGO_ALLOWED_HOSTS` (inclua `localhost,127.0.0.1` para testar de dentro da VM) |
| Login volta para a tela de login / erro 403 CSRF | `DJANGO_SECURE_COOKIES=true` com acesso por http, ou origem faltando em `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Container `web` reinicia em loop com "ERRO: DJANGO_SECRET_KEY..." | `.env` sem chave ou com menos de 50 caracteres |
| Acesso intermitente ao 10.11.10.10 | VM antiga ainda ligada com o mesmo IP |
| Tela sem estilo após atualizar | Cache do navegador: Ctrl+F5 |
