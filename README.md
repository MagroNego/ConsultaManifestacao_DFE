# Consulta de Manifestação — v2.0 Web

Aplicação corporativa para consultar o histórico local de manifestações de NF-e, gerar Excel e sincronizar o banco com o **NFeDistribuicaoDFe**.

A v2 mantém o núcleo Python da v1, mas adiciona uma interface Web para uso na rede interna da empresa.

## Fluxos separados

A aplicação possui três ações distintas:

- **Excel**: usa somente o banco local. O usuário seleciona um `CHAVES.txt` e recebe a planilha.
- **Consulta rápida**: busca pelo número da NF diretamente no banco local e mostra os eventos encontrados, sem acessar a SEFAZ.
- **Status**: lê o estado da última gravação no banco, incluindo `ultNSU`, `maxNSU` e disponibilidade da próxima sincronização.
- **Atualizar**: sincroniza somente o banco com a SEFAZ. Não recebe TXT e não gera Excel.

A área **Atualizar** é protegida por um único login administrativo. Excel, Consulta rápida e Status não exigem login adicional.

## Cooldown SEFAZ

Após uma tentativa válida de sincronização, a aplicação grava um bloqueio padrão de **120 minutos** no próprio banco.

O bloqueio:

- é validado no backend;
- sobrevive a reinícios do serviço;
- também é aplicado pela CLI da v2;
- não substitui o tratamento específico da rejeição 656.

## Interface Web

Instalação:

```powershell
py -m pip install -e .
```

Execução:

```powershell
nfe-consulta-web
```

ou:

```powershell
INICIAR_WEB.cmd
```

Em produção, a aplicação deve ficar atrás de um reverse proxy corporativo para HTTPS e publicação na rede interna. Consulte `SERVIDOR_WEB.md`.

## CLI

```powershell
nfe-consulta atualizar --banco dados\nfe_manifestacoes_seguro.db
nfe-consulta excel entrada\CHAVES.txt --banco dados\nfe_manifestacoes_seguro.db --saida saidas\Consulta_Manifestacao_YAB.xlsx
nfe-consulta status --banco dados\nfe_manifestacoes_seguro.db
```

- `atualizar`: somente SEFAZ → banco.
- `excel`: somente banco + TXT → XLSX.
- `status`: somente leitura do banco.

## Acesso administrativo

Somente a área **Atualizar** exige login. O usuário interno acessa normalmente Excel, Consulta rápida e Status.

O login administrativo usa:

```text
NFE_ADMIN_USER_FILE=C:\ConsultaManifestacao\secrets\admin-user.txt
NFE_ADMIN_PASSWORD_FILE=C:\ConsultaManifestacao\secrets\admin-password.txt
NFE_ADMIN_SESSION_MINUTES=30
```

O projeto inclui `CONFIGURAR_ADMIN.cmd`, que grava o usuário e a senha em `secrets\admin-user.txt` e `secrets\admin-password.txt`. Esses arquivos não são versionados. A senha não deve ser gravada no código nem enviada ao GitHub. Em produção, use ACL restrita no Windows.

A sessão usa cookie assinado, `HttpOnly`, `SameSite=Strict` e expira após o período configurado de inatividade. Alterar o HTML ou chamar diretamente a rota de sincronização não libera acesso sem sessão administrativa válida.

## Tema

A interface possui modo claro e escuro. A preferência é salva localmente no navegador.

## Certificado

A v2 aceita certificado Windows em:

```text
Cert:\CurrentUser\My
Cert:\LocalMachine\My
```

Para servidor corporativo, `LocalMachine` é o cenário recomendado, com a conta do serviço autorizada a ler a chave privada.

O certificado pode ser fixado por thumbprint.

## Banco

SQLite/SQLCipher continua suportado na primeira versão Web.

Enquanto SQLite for utilizado:

- execute somente **1 worker**;
- mantenha um único arquivo de banco ativo;
- faça backup regular.

Caso a aplicação evolua para múltiplas instâncias, alta disponibilidade ou concorrência maior, a persistência deve ser migrada para SQL Server ou PostgreSQL.

## Segurança

A v2 inclui:

- autorização no backend;
- proteção CSRF;
- headers HTTP de segurança;
- limite de upload;
- sanitização e validação das chaves existentes;
- log de auditoria sem registrar as chaves de acesso;
- cooldown persistente para SEFAZ;
- SQLCipher opcional.

## Estrutura principal

```text
nfe_consulta/
  servico.py
  banco.py
  distribuicao.py
  certificado_windows.py
  web/
    app.py
    auth.py
    settings.py
    status_view.py
    uploads.py
    audit.py
    templates/
    static/
```

## Testes

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
```

A CI da branch `web/v2.0` executa a suíte em Windows e Linux.

Os testes automatizados não fazem consulta real à SEFAZ nem usam certificado real.
