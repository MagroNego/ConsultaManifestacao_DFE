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
| Versão desta preparação | 2.2.0-dev |

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
- alertas por e-mail para novos eventos de Operação não Realizada (210240), com destinatários administrados na área Atualizar e fila persistente no banco;
- emitente e indicação de cancelamento na consulta de manifestações e no Excel quando recebidos pela distribuição; registros antigos sem esses dados aparecem sem informação até novo retorno;
- últimas dez sincronizações na página Status, resumidas do log de auditoria (origem, resultado, lotes, manifestações novas e falha genérica), sem exibir usuário, IP ou detalhes internos;
- filtro opcional **Somente canceladas** na consulta e na exportação, sem alterar a listagem padrão;
- histórico administrativo restrito à área Atualizar com responsável, ação e resultado de sincronizações, contas e destinatários dos alertas;
- planilhas com formatação simples de trabalho, preservando colunas, filtros e chaves de NF-e como texto;
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

### Alertas de Operação não Realizada

O administrador cadastra até 20 endereços em **Atualizar → Alertas por e-mail**.
Somente eventos 210240 inseridos após o cadastro geram avisos; reprocessar um
evento já gravado não cria outra mensagem. A fila fica no banco central e as
tentativas de envio ocorrem após a sincronização manual ou automática. Uma falha
do SMTP não altera o cursor NSU: o aviso fica pendente e pode ser reenviado pelo
botão **Tentar enviar pendentes** na área administrativa. Uma interrupção entre
a aceitação pelo SMTP e a confirmação no banco pode resultar em duplicidade.

A TI deve configurar `NFE_SMTP_HOST`, `NFE_SMTP_PORT`, `NFE_SMTP_SECURITY`
(`starttls` ou `ssl`), `NFE_SMTP_FROM` e, se houver autenticação,
`NFE_SMTP_USER` com a senha em `secrets/smtp-password.txt`. Sem host e remetente,
nenhum envio é feito. O arquivo `WEB_CONFIG.example` serve como referência;
`INICIAR_WEB.cmd` não o carrega automaticamente. Faça um teste com servidor de
e-mail de homologação antes de usar endereços reais.

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

Esses arquivos servem para criar a primeira conta no primeiro acesso. O aplicativo
guarda apenas o hash da senha em `dados/admin_accounts.db`, separado do banco fiscal.
Em **Atualizar → Gerenciar acessos**, cadastre logins pessoais, desative a conta
inicial compartilhada e remova `secrets/admin-password.txt`. Faça backup do arquivo
`dados/admin_accounts.db` junto com os demais dados locais. A senha antiga não é
reimportada se já houver contas cadastradas. As sessões são encerradas ao desativar
uma conta ou trocar sua senha.

Arquivos em `secrets` e `dados` não devem ser versionados e devem ter ACL restrita no servidor.

As outras senhas de runtime são lidas exclusivamente de `secrets`. Variáveis de ambiente como `NFE_ADMIN_PASSWORD`, `NFE_DATABASE_PASSWORD` e `NFE_CERT_PASSWORD` não são usadas como fonte de senha.

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

Se o serviço estiver desligado no horário programado e voltar ainda no mesmo dia útil, a aplicação faz uma execução de recuperação. O disparo diário é registrado no próprio banco para que reinícios do serviço não repitam a mesma sincronização automática.

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

A versão estável atual é **v2.1.1**. O pacote da release contém o código e a documentação, sem banco, senhas ou certificado. O agendamento interno é desativado por padrão em desenvolvimento; para uso automático a instalação precisa permanecer em execução e a configuração deve ser validada pela TI.

Os pacotes de instalação são publicados em **GitHub Releases**. Para implantação, utilize o arquivo `ConsultaManifestacao_DFE-vX.Y.Z.zip`, e não os pacotes automáticos de source code gerados pelo GitHub.

## Histórico

- **v0.9.4**: versão legada preservada na branch `main`;
- **v1.0**: refatoração da arquitetura desktop e CLI;
- **v2.0.0**: interface Web corporativa, administração centralizada e publicação para rede interna.
- **v2.0.1**: centralização de segredos de runtime e ajustes de configuração/implantação.

- **v2.1.1**: consulta completa com filtros e exportação, retirada da CLI/GUI legadas, agendador interno, diagnóstico do NSU enviado e informado no erro 656.
