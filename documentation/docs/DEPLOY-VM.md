# Deploy em VM (Nutanix AHV) com Docker Compose

Sistema de Estoque ClearIT rodando numa VM única, no IP **10.11.10.10**
(o mesmo da antiga VM no VMware). App (Gunicorn + WhiteNoise) e Postgres em
containers; acesso em `http://10.11.10.10`.

> Alternativa: o mesmo sistema pode rodar no Kubernetes (NKP) com os manifests
> da pasta `nginx/`. Este guia cobre só a VM.

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

## 6. Backup diário

```bash
sudo mkdir -p /opt/estoque-backups && sudo chown $USER /opt/estoque-backups
crontab -e
```
```
0 2 * * * cd /opt/estoque && docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > /opt/estoque-backups/estoque-$(date +\%F).dump && find /opt/estoque-backups -name '*.dump' -mtime +30 -delete
```
Guarde cópias fora da VM (snapshot/Protection Domain do Nutanix ajuda, mas não
substitui o dump).

---

## 7. Atualizar a versão

```bash
cd /opt/estoque
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > ../estoque-backups/antes-update.dump
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
