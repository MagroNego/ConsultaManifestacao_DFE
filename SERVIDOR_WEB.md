# Implantação Web — v2.0

A v2 foi desenhada para rodar dentro da rede da empresa com **um único processo da aplicação** enquanto o banco for SQLite/SQLCipher.

## Arquitetura recomendada

```text
Usuário
  ↓ HTTPS
IIS / reverse proxy corporativo
  ↓ headers de identidade + segredo interno
Consulta de Manifestação (FastAPI)
  ↓
SQLite/SQLCipher + certificado Windows + SEFAZ
```

Não exponha o Uvicorn diretamente aos usuários em produção. O padrão do aplicativo é escutar apenas em `127.0.0.1:8080`.

## Perfis

### Usuário

Pode acessar:

- **Excel**: envia um ou vários TXT, ou seleciona uma pasta contendo TXT, e recebe a planilha.
- **Status**: consulta a última gravação do banco e o estado do NSU.

Não pode acessar **Atualizar**. O backend devolve HTTP 403 mesmo se a pessoa tentar abrir a URL manualmente.

### Administrador

Além de Excel e Status, pode usar:

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

## Variáveis obrigatórias em produção

```text
NFE_WEB_ENV=production
NFE_WEB_AUTH_MODE=proxy
NFE_WEB_PROXY_SECRET=<segredo aleatório com pelo menos 24 caracteres>
NFE_WEB_CSRF_SECRET=<segredo aleatório com pelo menos 32 caracteres>
NFE_WEB_ADMIN_USERS=admin1@empresa.local,admin2@empresa.local
NFE_DATABASE_PATH=C:\ConsultaManifestacao\dados\nfe_manifestacoes_seguro.db
NFE_CERT_STORE=LocalMachine
NFE_CERT_THUMBPRINT=<thumbprint do certificado A1>
```

Para banco SQLCipher, prefira apontar a senha por arquivo com ACL restrita:

```text
NFE_DATABASE_PASSWORD_FILE=C:\ConsultaManifestacao\secrets\db-password.txt
```

## Headers enviados pelo proxy

Por padrão a aplicação espera:

```text
X-NFE-User
X-NFE-Name
X-NFE-Proxy-Secret
```

O reverse proxy deve:

1. autenticar o usuário pela solução corporativa;
2. remover qualquer header `X-NFE-*` recebido do cliente;
3. inserir novamente os headers acima com dados confiáveis;
4. preencher `X-NFE-Proxy-Secret` com o mesmo segredo configurado no servidor da aplicação.

Sem o segredo correto, a aplicação rejeita a requisição.

Os nomes podem ser alterados com:

```text
NFE_WEB_USER_HEADER
NFE_WEB_NAME_HEADER
NFE_WEB_PROXY_SECRET_HEADER
```

## Certificado no Windows Server

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

A rejeição 656 continua tendo tratamento próprio.

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

- HTTPS e autenticação no reverse proxy;
- ACL da pasta de dados e de secrets;
- permissão da chave privada do A1;
- backup do banco;
- acesso de saída ao Ambiente Nacional da NF-e;
- proxy/firewall corporativo;
- teste integrado controlado com SEFAZ;
- restauração de backup;
- rotação dos segredos do proxy e CSRF.
