# Consulta de Manifestação NF-e

Aplicação corporativa para consulta de manifestações de NF-e, geração de relatórios em Excel e sincronização controlada com o serviço **NFeDistribuicaoDFe** da SEFAZ.

A versão Web foi projetada para uso em rede interna, com separação entre operações de consulta e ações administrativas.

## Visão geral

| Item | Tecnologia |
| --- | --- |
| Backend | FastAPI / Uvicorn |
| Interface | HTML, CSS e JavaScript |
| Persistência | SQLite / SQLCipher |
| Certificado | A1 PFX/P12 ou Windows Certificate Store |
| Plataforma alvo | Windows / Windows Server |
| Versão em desenvolvimento | 2.1.0-dev |

## Funcionalidades

- consulta completa do histórico por período, número da NF, série, chave e tipo de manifestação;
- exportação para Excel usando exatamente os filtros aplicados na consulta;
- paginação dos resultados na interface Web;
- geração de planilha Excel a partir de um arquivo `CHAVES.txt` para listas específicas;
- painel de status com `ultNSU`, `maxNSU` e disponibilidade da próxima sincronização;
- sincronização independente com o Ambiente Nacional da NF-e;
- cooldown persistente para controle de consumo da SEFAZ;
- tratamento específico para rejeição 656;
- autenticação administrativa para configuração e atualização;
- seleção e validação do banco central pela interface administrativa;
- seleção e validação de certificado A1 pela interface administrativa;
- log de auditoria com rotação;
- modo claro e escuro;
- sincronização automática interna da SEFAZ pela manhã, sem CLI ou Task Scheduler.

## Fluxo da aplicação

```text
Usuários internos
        |
        +-- Consulta ------> banco central
        |       |
        |       +-- filtros e paginação
        |       +-- exportação XLSX
        |       +-- CHAVES.txt
        |
        +-- Status --------> banco central
        |
        +-- Atualizar ----- login administrativo
                               |
                               +-- banco
                               +-- certificado A1
                               +-- SEFAZ
```

As operações de Consulta, exportação para Excel e Status não acessam a SEFAZ.

## Instalação

Requisitos:

- Windows 10/11 ou Windows Server;
- Python 3.11 ou superior;
- acesso HTTPS ao Ambiente Nacional da NF-e;
- certificado A1 válido;
- acesso ao banco SQLite/SQLCipher utilizado pela aplicação.

Execute:

```powershell
INSTALAR.cmd
```

O instalador cria o ambiente virtual e prepara as pastas locais necessárias.

Depois configure o acesso administrativo:

```powershell
CONFIGURAR_ADMIN.cmd
```

E inicie a aplicação:

```powershell
INICIAR_WEB.cmd
```

## Administração

A área **Atualizar** permite configurar os recursos utilizados pelo servidor.

### Banco de dados

O caminho validado é persistido em:

```text
secrets\db-path.txt
```

A senha SQLCipher permanece separada em:

```text
secrets\db-password.txt
```

### Certificado A1

A aplicação pode utilizar um certificado `.pfx` ou `.p12` armazenado em uma pasta protegida.

A configuração local utiliza:

```text
secrets\cert-path.txt
secrets\cert-password.txt
```

O certificado não é copiado para dentro do projeto.

### Credenciais administrativas

```text
secrets\admin-user.txt
secrets\admin-password.txt
```

Arquivos em `secrets` não devem ser versionados e devem ter ACL restrita no servidor.

As senhas de runtime são lidas exclusivamente dessa pasta. Variáveis de ambiente como `NFE_ADMIN_PASSWORD`, `NFE_DATABASE_PASSWORD` e `NFE_CERT_PASSWORD` não são usadas como fonte de senha.

## Segurança

A aplicação inclui:

- autorização no backend;
- proteção CSRF;
- cookie administrativo assinado, `HttpOnly` e `SameSite=Strict`;
- headers HTTP de segurança;
- validação de uploads;
- separação de credenciais e arquivos de configuração;
- SQLCipher para banco protegido;
- auditoria sem registrar chaves de NF-e ou credenciais;
- limite de uma sincronização simultânea.

O pacote de release não contém banco, senhas ou certificado A1.

## Implantação

Para ambiente corporativo, a arquitetura recomendada é:

```text
Rede interna
    |
   HTTPS
    |
   IIS
    |
127.0.0.1:8080
    |
FastAPI / Uvicorn
    |
SQLite / SQLCipher
```

Enquanto SQLite/SQLCipher for utilizado, execute a aplicação com **1 worker** e mantenha o banco em disco local do servidor sempre que possível.

As instruções de implantação estão em `SERVIDOR_WEB.md`.

## Sincronização automática

A v2.1 não utiliza CLI nem `ATUALIZAR_BANCO_MANHA.cmd`.

O próprio processo Web mantém um agendador interno para sincronização com a SEFAZ. Em produção, o padrão é executar às **08:00 de segunda a sexta-feira**, usando o mesmo banco, certificado, cooldown e trava da sincronização manual.

Configurações operacionais:

```text
NFE_AUTO_SYNC_ENABLED=1
NFE_AUTO_SYNC_HOUR=8
NFE_AUTO_SYNC_MINUTE=0
NFE_AUTO_SYNC_WEEKDAYS=0,1,2,3,4
NFE_AUTO_SYNC_MAX_LOTES=50
```

Segunda-feira é `0` e domingo é `6`.

Em ambiente de desenvolvimento o agendador fica desativado por padrão. Em produção, fica ativado por padrão e pode ser desligado com `NFE_AUTO_SYNC_ENABLED=0`.

A execução automática aparece no mesmo log de auditoria da aplicação com a ação `sefaz_sync_auto`.

## Desenvolvimento

Instale as dependências de desenvolvimento:

```powershell
py -m pip install -e ".[dev]"
```

Execute a suíte:

```powershell
py -m pytest -q
```

A integração contínua valida o projeto em Windows e Linux.

Os testes automatizados não acessam a SEFAZ real e não utilizam certificado de produção.

## Releases

A versão estável atual é **v2.0.1**. A branch `web/v2.1` contém o desenvolvimento da próxima versão, ainda não publicada.

Os pacotes de instalação são publicados em **GitHub Releases**. Para implantação, utilize o arquivo `ConsultaManifestacao_DFE-vX.Y.Z.zip`, e não os pacotes automáticos de source code gerados pelo GitHub.

## Histórico

- **v0.9.4**: versão legada preservada na branch `main`;
- **v1.0**: refatoração da arquitetura desktop e CLI;
- **v2.0.0**: interface Web corporativa, administração centralizada e publicação para rede interna.
- **v2.0.1**: centralização de segredos de runtime e ajustes de configuração/implantação.

- **v2.1.0**: consulta completa com filtros, exportação do resultado para Excel, remoção integral da CLI/GUI legadas e sincronização automática interna (em desenvolvimento).
