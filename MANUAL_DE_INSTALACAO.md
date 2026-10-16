# Instalação e atualização

## Requisitos

| Requisito | Especificação |
| --- | --- |
| Produção com SEFAZ | Windows 10/11 ou Windows Server; PowerShell disponível |
| Python | 3.11+; versão usada na CI: 3.12 |
| Instalação Windows | Python Launcher `py` e acesso ao índice de dependências Python |
| Banco | Banco de manifestações existente e compatível, SQLite/SQLCipher |
| Certificado | A1 válido, PFX/P12 ou Windows Certificate Store; chave privada acessível ao processo |
| Rede | HTTPS para o endpoint SEFAZ; SMTP se houver alertas |
| Permissões | Leitura do certificado e escrita em banco, `dados`, `secrets` e `logs` |

A instalação não fornece certificado, senha, banco fiscal preenchido ou credenciais SMTP. O CNPJ e a UF padrão desta distribuição estão em `nfe_consulta/config.py`; valide-os antes de usar o app para outra empresa. O banco selecionado deve conter a tabela `manifestacoes`; um arquivo SQLite vazio não atende à configuração administrativa.

## Windows: instalação

Extraia o pacote em `C:\AtlasDFE` ou outra pasta definitiva com permissão de escrita. No PowerShell:

```powershell
Set-Location C:\AtlasDFE
py --version
.\INSTALAR.cmd
.\CONFIGURAR_ADMIN.cmd
.\INICIAR_WEB.cmd
```

`INSTALAR.cmd` cria `.venv`, instala as dependências e prepara `dados`, `secrets` e `logs`. `CONFIGURAR_ADMIN.cmd` solicita usuário e senha de pelo menos 12 caracteres, grava o hash e preserva as outras contas. Em banco de contas existente, cria um backup antes da alteração.

O lançador inicia em produção, gera `secrets/web-csrf-secret.txt` se necessário e ativa a sincronização automática quando a variável não foi definida. Para configurar inicialmente sem disparos automáticos:

```powershell
$env:NFE_AUTO_SYNC_ENABLED = "0"
.\INICIAR_WEB.cmd
```

## Configuração inicial

1. Acesse `http://127.0.0.1:8080` e entre com a conta administrativa.
2. Em **Admin**, selecione o banco fiscal existente. O caminho padrão é `dados/nfe_manifestacoes_seguro.db`; a seleção salva em `secrets/db-path.txt` prevalece.
3. Para SQLCipher, disponibilize a senha em `secrets/db-password.txt`. Usuários comuns não informam essa senha.
4. Configure o certificado A1 por arquivo ou repositório Windows. O arquivo PFX/P12 permanece no caminho selecionado; não é copiado para o projeto.
5. Confira banco, última gravação, `ultNSU` e `maxNSU` em **Status**.
6. Se houver alertas, configure SMTP e destinatários e use **Enviar e-mail de teste**.
7. Confirme a configuração ativa do Qive antes de habilitar a captura conjunta. Consulte [Distribuição e Qive](DISTRIBUICAO_DFE_QIVE.md).

Para ativar a rotina, pare o processo com `Ctrl+C` e inicie novamente:

```powershell
$env:NFE_AUTO_SYNC_ENABLED = "1"
$env:NFE_RECOVERY_ENABLED = "0"
.\INICIAR_WEB.cmd
```

As variáveis acima valem para esse PowerShell e os processos iniciados por ele. Para serviço Windows, configure-as no ambiente do serviço. `WEB_CONFIG.example` é uma referência e **não é carregado automaticamente**.

## Janela e disponibilidade

A janela é **22:00 inclusive até 04:00 exclusiva, Brasília (UTC−3)**. Os disparos ocorrem às **22h, 23h, 00h, 01h, 02h e 03h**, todos os dias por padrão. Consultas manuais e retentativas também respeitam janela, trava e cooldown de 60 minutos. Não há disparo às 04h.

Mantenha o computador sem suspensão/hibernação e o app em execução. Fechar o terminal encerra a aplicação. O agendador não liga o computador nem inicia sozinho um processo encerrado. Use um serviço do sistema operacional para inicialização automática, conforme [Servidor Web](SERVIDOR_WEB.md).

## Linux: consultas locais e desenvolvimento

A interface, importação e relatórios locais executam em Linux. O cliente SEFAZ e a leitura de A1 dependem do executável PowerShell usado pelo código; não considere a sincronização Linux homologada por este procedimento. Mantenha-a desabilitada.

Instale Python com suporte a `venv`, compilador e bibliotecas de desenvolvimento SQLCipher exigidas pelo pacote `sqlcipher3`. Na pasta do projeto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
mkdir -p secrets dados logs
chmod 700 secrets dados logs
.venv/bin/python -m nfe_consulta.web.configure_admin
.venv/bin/python -c "from pathlib import Path; import secrets; p=Path('secrets/web-csrf-secret.txt'); p.exists() or p.write_text(secrets.token_urlsafe(48), encoding='utf-8')"
chmod 600 secrets/*
env NFE_WEB_ENV=production NFE_AUTO_SYNC_ENABLED=0 NFE_RECOVERY_ENABLED=0 .venv/bin/python -m nfe_consulta.web.app
```

## Atualização por Git

Pare o app e faça o [backup](SEGURANCA_BANCO.md). Na pasta do repositório:

```powershell
git status --short
git branch --show-current
git switch main
git pull --ff-only origin main
.\INSTALAR.cmd
.\INICIAR_WEB.cmd
```

Se houver alterações locais ou divergência, resolva-as antes de atualizar; não use `reset --hard` para descartar arquivos da instalação. O `git pull` atualiza código, não o processo já aberto.

## Atualização por ZIP

1. Pare o app e faça backup do banco fiscal, inclusive quando estiver fora da pasta do projeto.
2. Extraia o pacote novo em pasta temporária.
3. Substitua `nfe_consulta` por inteiro e atualize `pyproject.toml`, lançadores, configuração de exemplo e documentação.
4. Preserve `dados`, `secrets`, `logs`, certificado, entradas e saídas. Preserve `.venv` e atualize suas dependências pelo instalador.
5. Execute `INSTALAR.cmd` e reinicie com `INICIAR_WEB.cmd`.

Em ambos os métodos, confira login, versão, banco, certificado e cursores. Use `Ctrl+F5` no navegador para recarregar os recursos da interface. Não zere o NSU nem apague pendências para validar a atualização. Remova lançadores de teste antigos e variáveis de agendamento legadas descritas em [Servidor Web](SERVIDOR_WEB.md).

## Diagnóstico de instalação

| Sintoma | Verificação |
| --- | --- |
| `py` não encontrado | Instalar Python Launcher; reabrir o terminal |
| Falha ao instalar SQLCipher | Conferir a saída do pip e as dependências nativas da plataforma |
| Banco indisponível | Caminho selecionado, permissões e senha SQLCipher |
| Certificado indisponível | Validade, chave privada, senha e conta que executa o processo |
| Token de segurança inválido | Atualizar a página e entrar novamente antes de repetir a ação |
| Sincronização não inicia | Horário Brasília, processo ativo, variável de ativação e próxima tentativa em Status |
| Porta ocupada | Verificar outra instância antes de mudar a porta; manter um único processo |
