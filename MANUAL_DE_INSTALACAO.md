# Instalação no Windows — Consulta de Manifestação NF-e

A aplicação é distribuída como serviço Web interno. A interface de uso é acessada pelo navegador.

## Requisitos

- Windows 10/11 ou Windows Server;
- Python 3.11 ou superior;
- acesso HTTPS ao Ambiente Nacional da NF-e para a rotina de sincronização;
- certificado A1 válido;
- banco SQLite/SQLCipher existente;
- permissão de leitura e escrita nas pastas da aplicação.

## Instalação

Extraia o pacote em uma pasta definitiva, por exemplo:

```text
C:\ConsultaManifestacao
```

Execute:

```powershell
INSTALAR.cmd
```

O instalador:

1. cria o ambiente virtual `.venv`;
2. instala as dependências;
3. cria as pastas `dados`, `secrets` e `logs`;
4. valida o runtime Web.

## Configuração inicial

Configure o acesso administrativo:

```powershell
CONFIGURAR_ADMIN.cmd
```

Depois inicie a aplicação:

```powershell
INICIAR_WEB.cmd
```

Acesse a área **Atualizar** para configurar o banco central e o certificado A1.

## Segredos

As credenciais de runtime são lidas da pasta:

```text
secrets\
```

Arquivos principais:

```text
admin-user.txt
admin-password.txt
db-path.txt
db-password.txt
cert-path.txt
cert-password.txt
```

A pasta deve ter ACL NTFS restrita à conta que executa a aplicação e aos administradores autorizados.

## Produção

Em ambiente corporativo, publique a aplicação atrás de IIS/HTTPS e mantenha o Uvicorn em `127.0.0.1:8080`.

A sincronização automática da manhã roda dentro do próprio processo Web. Em produção, o padrão é segunda a sexta-feira às 08:00:

```text
NFE_AUTO_SYNC_ENABLED=1
NFE_AUTO_SYNC_HOUR=8
NFE_AUTO_SYNC_MINUTE=0
NFE_AUTO_SYNC_WEEKDAYS=0,1,2,3,4
NFE_AUTO_SYNC_MAX_LOTES=50
```

O serviço Web precisa permanecer ativo no horário programado.

Consulte `SERVIDOR_WEB.md` para detalhes de implantação.

## Validação

Para executar a suíte automatizada:

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
```

Os testes automatizados não acessam a SEFAZ real nem utilizam certificado de produção.
