# AtlasDFE — início rápido

## Instalar no Windows

1. Instale Python 3.11+ com o Python Launcher (`py`).
2. Extraia o pacote em uma pasta definitiva.
3. Execute `INSTALAR.cmd`.
4. Execute `INICIAR_WEB.cmd` e acesse `http://127.0.0.1:8080`.
5. Abra **Admin**; configure o banco de manifestações existente e o certificado A1.
6. Confira **Status** e, se necessário, configure **Admin → Alertas por e-mail**.

O app não exige login ou senha de administrador. O TI deve controlar o acesso ao endereço, incluindo a área Admin.

## Rotina

- **AtlasDFE:** 22:00 até antes de 04:00, Brasília. Disparos às 22h, 23h, 00h, 01h, 02h e 03h.
- **Qive:** janela solicitada de 08:00–18:00, incluindo retentativas. A aplicação não verifica a configuração do Qive.
- **consNSU:** pausado por padrão; pendências preservadas.
- Mantenha o computador ligado, sem suspensão/hibernação, e o processo Web ativo. Bloquear a sessão com `Win+L` não encerra o processo; sair da sessão pode encerrá-lo.
- Importações, consultas locais e relatórios continuam disponíveis durante o dia.

## Atualizar

Pare o app, faça backup e siga [Instalação](MANUAL_DE_INSTALACAO.md). Preserve banco fiscal, `dados`, `secrets`, certificado e logs. Após reiniciar, confira versão, acesso e cursores em **Status**.

[Uso](MANUAL_DE_USO.md) · [Distribuição e Qive](DISTRIBUICAO_DFE_QIVE.md) · [Backup](SEGURANCA_BANCO.md)
