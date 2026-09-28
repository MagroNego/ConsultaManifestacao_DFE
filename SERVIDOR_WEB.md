# Implantação Web — v2.1.1

A v2 foi desenhada para rodar dentro da rede da empresa com **um único processo da aplicação** enquanto o banco for SQLite/SQLCipher.

## Arquitetura recomendada

```text
Usuário
  ↓ HTTPS
IIS / reverse proxy corporativo
  ↓
Consulta de Manifestação (FastAPI)
  ↓
SQLite/SQLCipher + certificado Windows + SEFAZ
```

Não exponha o Uvicorn diretamente aos usuários em produção. O padrão do aplicativo é escutar apenas em `127.0.0.1:8080`.

## Perfis

### Usuário

Pode acessar:

- **Consulta**: pesquisa o histórico do banco por período, NF, série, chave e manifestação, com exportação para Excel.
- **Status**: consulta a última gravação do banco e o estado do NSU.

Ao abrir **Atualizar**, o sistema solicita o login administrativo.

### Administrador

Após autenticar com o único login administrativo, pode usar:

- **Atualizar**: sincroniza o banco com `NFeDistribuicaoDFe`.

Após uma tentativa válida de sincronização, a aplicação grava um cooldown padrão de **120 minutos** no banco. O bloqueio sobrevive a reinícios do serviço.

## Instalação

Use Python 3.11 ou superior:

```powershell
py -m pip install -e .
nfe-consulta-web
```

Para validação antes de produção:

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
```

## Configuração de produção

As senhas não são fornecidas por variável de ambiente. A aplicação lê exclusivamente os arquivos locais da pasta `secrets`:

```text
C:\ConsultaManifestacao\secrets\admin-user.txt
C:\ConsultaManifestacao\secrets\admin-password.txt
C:\ConsultaManifestacao\secrets\db-password.txt
C:\ConsultaManifestacao\secrets\cert-path.txt
C:\ConsultaManifestacao\secrets\cert-password.txt
C:\ConsultaManifestacao\secrets\db-path.txt
```

Variáveis como `NFE_ADMIN_PASSWORD`, `NFE_DATABASE_PASSWORD` e `NFE_CERT_PASSWORD` não são usadas como fallback.

As variáveis de ambiente continuam disponíveis apenas para configuração não sensível ou operacional, por exemplo:

```text
NFE_WEB_ENV=production
NFE_WEB_CSRF_SECRET=<segredo aleatório com pelo menos 32 caracteres>
NFE_ADMIN_SESSION_MINUTES=30
NFE_CERT_STORE=LocalMachine
NFE_CERT_THUMBPRINT=<thumbprint, se usar Windows Certificate Store>
NFE_SEFAZ_COOLDOWN_MINUTES=120
```

Os arquivos em `secrets` devem ter ACL restrita à conta que executa a aplicação. Rode `CONFIGURAR_ADMIN.cmd` para criar o login administrativo. O arquivo `db-password.txt` deve conter somente a senha do SQLCipher.

O reverse proxy continua recomendado para HTTPS e publicação na rede interna, mas não precisa autenticar cada funcionário. A autenticação adicional existe apenas na aba **Atualizar**.

## Certificado no Windows Server

### Arquivo PFX/P12 protegido

O cenário preferido desta versão é manter o A1 na pasta restrita definida pela TI e configurar o caminho pela aba **Atualizar**.

Exemplo:

```text
C:\TI\Certificados\Yorozu\certificado.pfx
```

O arquivo permanece nesse local. A aplicação salva apenas:

```text
secrets\cert-path.txt
secrets\cert-password.txt
```

A conta do serviço precisa ter leitura no PFX. Restrinja também a ACL da pasta `secrets`.

A sincronização automática usa a mesma configuração feita na área administrativa.

### Windows Certificate Store



Para serviço corporativo é recomendado:

```text
NFE_CERT_STORE=LocalMachine
```

Instale o certificado A1 em:

```text
Cert:\LocalMachine\My
```

A conta que executa a aplicação precisa ter permissão de leitura sobre a chave privada do certificado.

O certificado pode ser fixado por thumbprint usando `NFE_CERT_THUMBPRINT`. Isso evita seleção ambígua caso o servidor possua vários certificados.

## Cooldown SEFAZ

O padrão é 120 minutos:

```text
NFE_SEFAZ_COOLDOWN_MINUTES=120
```

O cooldown é validado no backend e gravado no banco. Alterar HTML, chamar a rota manualmente ou reiniciar a aplicação não elimina o bloqueio.

A rejeição 656 registra uma pausa no banco e, quando a resposta o informa,
mostra o último NSU indicado pela SEFAZ. O cursor local não é avançado na
rejeição.

## Rede

A aplicação deve escutar apenas na interface usada pelo reverse proxy. Padrão:

```text
NFE_WEB_HOST=127.0.0.1
NFE_WEB_PORT=8080
NFE_WEB_FORWARDED_ALLOW_IPS=127.0.0.1
```

Se o proxy estiver em outra máquina, `NFE_WEB_FORWARDED_ALLOW_IPS` deve conter apenas os endereços confiáveis do proxy.

## Banco

Enquanto SQLite/SQLCipher for usado, execute **1 worker** da aplicação. O comando `nfe-consulta-web` já inicia dessa forma.

Se a aplicação precisar de múltiplas instâncias, alta disponibilidade ou grande concorrência, migre a persistência para SQL Server/PostgreSQL antes de aumentar a quantidade de workers.

## Auditoria

O log padrão fica em:

```text
logs\web_audit.log
```

Pode ser alterado por:

```text
NFE_WEB_AUDIT_LOG
```

O log registra usuário, ação, resultado e informações operacionais. Ele não grava as chaves de acesso enviadas.

## Tema

A interface possui modo claro e escuro. A preferência é salva no próprio navegador e não precisa ser armazenada no servidor.

## Health check

```text
GET /healthz
```

Retorna somente estado básico, versão e disponibilidade do arquivo de banco.

## Antes de produção

A TI ainda deve validar:

- HTTPS e publicação interna no reverse proxy;
- ACL da pasta de dados e de secrets;
- permissão da chave privada do A1;
- backup do banco;
- acesso de saída ao Ambiente Nacional da NF-e;
- proxy/firewall corporativo;
- teste integrado controlado com SEFAZ;
- restauração de backup;
- rotação da senha administrativa e do segredo CSRF.


## Sincronização automática

A v2.1 executa a rotina matinal dentro do próprio processo Web. Não existe CLI pública, BAT de atualização nem dependência do Agendador de Tarefas do Windows.

Em produção, o padrão é:

```text
segunda a sexta-feira
08:00
50 lotes no máximo
```

Configuração:

```text
NFE_AUTO_SYNC_ENABLED=1
NFE_AUTO_SYNC_HOUR=8
NFE_AUTO_SYNC_MINUTE=0
NFE_AUTO_SYNC_WEEKDAYS=0,1,2,3,4
NFE_AUTO_SYNC_MAX_LOTES=50
```

Segunda-feira é `0` e domingo é `6`.

A rotina automática usa:

- o banco selecionado pela área administrativa;
- a senha SQLCipher em `secrets\db-password.txt`;
- o PFX/P12 configurado em `secrets\cert-path.txt` e `secrets\cert-password.txt`, ou o Windows Certificate Store;
- o mesmo cooldown persistente da sincronização manual;
- o mesmo lock de processo da rota administrativa.

Se uma sincronização manual já estiver em andamento, a execução automática é ignorada. Se o cooldown ainda estiver ativo, a rotina também é ignorada sem tentar contornar o bloqueio.

As execuções são registradas em:

```text
logs\web_audit.log
```

com a ação `sefaz_sync_auto`.

Em desenvolvimento, o agendador fica desligado por padrão; em produção, fica ligado por padrão.

Se o serviço estiver indisponível às 08:00 e voltar depois desse horário no mesmo dia útil, a aplicação tenta recuperar a execução perdida. O controle diário fica persistido na tabela `controle_agendamento`, evitando que reinicializações do processo provoquem múltiplos disparos automáticos no mesmo dia.

## Banco central configurado pela área administrativa

Na aba **Atualizar**, o administrador informa o caminho do banco SQLite/SQLCipher existente no servidor. A aplicação valida o arquivo antes de ativá-lo e persiste somente o caminho em:

```text
secrets\db-path.txt
```

A senha permanece em:

```text
secrets\db-password.txt
```

O mesmo caminho é utilizado pelas telas Web e pela sincronização automática interna. A conta do serviço precisa ter leitura e escrita no banco. Para SQLite/SQLCipher, mantenha o arquivo em disco local do servidor sempre que possível.
