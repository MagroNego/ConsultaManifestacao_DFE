# Manual de instalação — v2.2.0

## Requisitos

- Python 3.11 ou superior e acesso às dependências Python.
- Windows 10/11, Windows Server ou Linux.
- Banco de manifestações existente e acesso de leitura/escrita para a conta do processo.
- Certificado A1 válido para a sincronização: PFX/P12 ou Windows Certificate Store.
- Acesso HTTPS ao Ambiente Nacional da NF-e.

## Windows

Extraia `ConsultaManifestacao_DFE-v2.2.0.zip`, por exemplo em `C:\ConsultaManifestacao`.

```powershell
.\INSTALAR.cmd
.\CONFIGURAR_ADMIN.cmd
.\INICIAR_WEB.cmd
```

O instalador cria `.venv`, instala as dependências e prepara as pastas operacionais. O configurador cria as credenciais da primeira conta. O lançador inicia em modo produção, cria o segredo Web persistente quando necessário e habilita a rotina de oito horas.

Abra http://127.0.0.1:8080. Em **Atualizar**, autentique-se, selecione o banco e configure o certificado. Para SQLCipher, coloque a senha em `secrets\db-password.txt`. Usuários comuns não informam essa senha na consulta.

## Linux

Na pasta extraída:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
mkdir -p secrets dados logs
chmod 700 secrets dados logs
```

Crie `secrets/admin-user.txt` e `secrets/admin-password.txt` em um editor local. A senha inicial deve ter pelo menos 12 caracteres. Gere o segredo Web:

```bash
.venv/bin/python -c "from pathlib import Path; import secrets; p=Path('secrets/web-csrf-secret.txt'); p.exists() or p.write_text(secrets.token_urlsafe(48), encoding='utf-8')"
chmod 600 secrets/*
```

Inicie com:

```bash
NFE_WEB_ENV=production NFE_AUTO_SYNC_ENABLED=1 NFE_AUTO_SYNC_INTERVAL_HOURS=8 .venv/bin/python -m nfe_consulta.web.app
```

Em fish:

```fish
env NFE_WEB_ENV=production NFE_AUTO_SYNC_ENABLED=1 NFE_AUTO_SYNC_INTERVAL_HOURS=8 .venv/bin/python -m nfe_consulta.web.app
```

Configure o certificado por arquivo PFX/P12 em **Atualizar**. O Windows Certificate Store está disponível somente no Windows.

## Atualizar uma instalação existente

1. Pare o processo Web e faça backup da instalação e do banco configurado, inclusive se estiver fora da pasta do projeto.
2. Extraia a release em uma pasta temporária.
3. Substitua `nfe_consulta` por inteiro e atualize `pyproject.toml`, os arquivos `.cmd`, `WEB_CONFIG.example` e os manuais.
4. Preserve `dados`, `secrets`, `logs`, arquivos de entrada/saída e o certificado. Preserve também `.venv`; as dependências serão atualizadas pelo instalador.
5. Remova o antigo `TESTAR_SYNC_30-09_09H.cmd` e qualquer variável `NFE_AUTO_SYNC_ONCE_DATE` do processo de inicialização.
6. Execute `INSTALAR.cmd` no Windows ou `.venv/bin/python -m pip install -e .` no Linux.
7. Reinicie, confirme a versão **2.2.0** e compare `ultNSU`, `maxNSU` e última gravação em **Status** com os dados anteriores.

As tabelas adicionais são criadas pelo aplicativo sem apagar o histórico existente. Não avance nem zere o cursor NSU manualmente durante a atualização.

## Configuração operacional

A rotina final usa **00:00, 08:00 e 16:00, horário de Brasília, todos os dias**. `INICIAR_WEB.cmd` aplica a ativação se `NFE_AUTO_SYNC_ENABLED` não estiver definida. Para desativar no PowerShell antes de iniciar:

```powershell
$env:NFE_AUTO_SYNC_ENABLED = "0"
.\INICIAR_WEB.cmd
```

No Linux, a ativação é definida no ambiente do serviço conforme o comando acima. `WEB_CONFIG.example` é uma referência; não é carregado automaticamente.

Execute uma única instância. O processo precisa permanecer ativo; feche-o de forma controlada antes de substituir código ou restaurar backups. Consulte [SERVIDOR_WEB.md](SERVIDOR_WEB.md) para HTTPS e execução como serviço.
