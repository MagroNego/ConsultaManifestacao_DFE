# Consulta de Manifestação NF-e

Aplicação Web para consultar manifestações de NF-e, exportar relatórios Excel e sincronizar o histórico com o serviço **NFeDistribuicaoDFe** do Ambiente Nacional da NF-e.

**Versão 2.4.0** · Python 3.11+ · Windows e Linux

## Funcionalidades

- Consulta por período do evento, número da nota, chave de acesso e manifestação.
- Resultados paginados e exportação Excel com os mesmos filtros, abrangendo todas as páginas.
- Exportação por arquivo TXT com uma chave de 44 dígitos por linha.
- Identificação do emitente pelo nome recebido ou pelo CNPJ da chave.
- Status do banco, cursor NSU, bloqueio e últimas sincronizações.
- Sincronização manual administrativa e automática às **08:00 e 15:00 (Brasília)**.
- Consulta e exportações sem login; Admin protegido por conta e senha.
- Alertas de novos eventos **Operação não Realizada (210240)** por e-mail, com fila persistente.
- Leitor XML integrado: importação cumulativa de XML/ZIP mensal, busca, itens, retenções, Excel e CSV.
- Download do XML original na consulta de manifestações, associado pela chave de acesso.
- Interface em português, com modos claro e escuro.

Consulta, Status e exportações usam o banco local e não fazem chamadas à SEFAZ. A aplicação consulta manifestações; não emite eventos de manifestação nem apresenta a situação de autorização ou cancelamento das notas.

## Instalação no Windows

Baixe `ConsultaManifestacao_DFE-v2.4.0.zip` em [Releases](https://github.com/MagroNego/ConsultaManifestacao_DFE/releases), extraia em uma pasta definitiva e execute, nesta ordem:

```powershell
.\INSTALAR.cmd
.\CONFIGURAR_ADMIN.cmd
.\INICIAR_WEB.cmd
```

Abra **http://127.0.0.1:8080**. Em **Admin**, configure o banco existente e o certificado A1. O certificado pode ser um PFX/P12 protegido ou estar instalado no repositório de certificados do Windows.

O lançador Windows inicia em modo produção e habilita a sincronização nos horários fixos de 08:00 e 15:00. Para desligá-la, defina `NFE_AUTO_SYNC_ENABLED=0` antes de executar o lançador. Banco, certificado e credenciais são configurados na instalação e não acompanham o pacote.

Para Linux e atualização de uma instalação existente, consulte o [manual de instalação](MANUAL_DE_INSTALACAO.md).

## Sincronização automática

A rotina executa às **08:00 e 15:00, horário de Brasília, todos os dias**. O processo Web precisa permanecer ativo. O agendamento independe do horário em que o aplicativo foi iniciado.

```text
NFE_AUTO_SYNC_ENABLED=1
NFE_AUTO_SYNC_WEEKDAYS=0,1,2,3,4,5,6
NFE_AUTO_SYNC_MAX_LOTES=50
```

A conclusão de cada janela é registrada no banco para evitar repetição após reiniciar. Se o servidor voltar depois de um horário programado, recupera apenas a janela mais recente ainda não concluída. Falhas e resultados parciais são retomados na próxima janela, respeitando o cooldown persistente. Após reiniciar, recupera apenas a janela mais recente do dia atual; antes das 08:00, aguarda a primeira janela. A rotina manual e a automática compartilham a mesma trava e o mesmo cursor NSU.

O cooldown padrão é **60 minutos**. A configuração antiga de cooldown é ignorada: o servidor usa 60 minutos. Bloqueios já persistidos são preservados até expirar. A rejeição 656 registra uma pausa sem avançar o cursor com base na rejeição.

## Lotes mensais de XML

Abra **Admin → Importar XML** e envie o ZIP baixado do Synchro ou vários XMLs completos. Os documentos ficam arquivados no banco fiscal, preservando os meses anteriores e ignorando chaves repetidas. Consulte por emissão, número, chave ou destinatário; abra itens e retenções e exporte Excel/CSV. Na Consulta, **Baixar XML** aparece quando a chave tem arquivo importado.

O leitor foi integrado a partir de [Leitor_XML_Saida](https://github.com/MagroNego/Leitor_XML_Saida). Aceita NF-e modelo 55 emitidas pelo CNPJ do aplicativo. A importação é local, sem certificado e sem chamadas à SEFAZ. Faça backup do banco fiscal para preservar também os XMLs; SQLCipher protege os novos dados quando habilitado. Veja limites e detalhes no [manual de uso](MANUAL_DE_USO.md).

## Administração e segurança

Consulta, Status, XML e exportações não exigem login. **Admin** exige uma conta administrativa: importação de XML, sincronização manual, configuração e histórico são protegidos no servidor, inclusive por URLs diretas. `CONFIGURAR_ADMIN.cmd` cria ou redefine a conta escolhida, preserva as demais e faz backup do banco de contas antes de alterar uma instalação existente.

A senha fica como hash em `dados/admin_accounts.db` (ou `NFE_ADMIN_ACCOUNTS_PATH`). Sessões são mantidas no servidor, expiram por inatividade e são revogadas no logout ou na redefinição da senha. O cookie é `HttpOnly` e `SameSite=Strict`; em HTTPS também usa `Secure`. Em HTTP local, o login funciona sem esse atributo; use HTTPS no servidor definitivo.

- Proteção CSRF nos formulários.
- SQL parametrizado, processamento XML com `defusedxml` e limites de upload/exportação.
- Auditoria com rotação em `logs/web_audit.log`.
- SQLCipher opcional para proteger o banco fiscal; a administração mostra o modo de armazenamento.

Senhas do banco, certificado e SMTP ficam em `secrets`. Contas administrativas antigas continuam disponíveis; contas sem perfil Admin não entram nessa área. As credenciais não são incluídas nas releases.

Em rede interna, use HTTPS por reverse proxy e **um único processo/worker**. Consulte [implantação](SERVIDOR_WEB.md) e [segurança do banco](SEGURANCA_BANCO.md).

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [Leia primeiro](LEIA_PRIMEIRO.md) | Início rápido |
| [Instalação](MANUAL_DE_INSTALACAO.md) | Windows, Linux e atualização |
| [Uso](MANUAL_DE_USO.md) | Consulta, Excel, Status e administração |
| [Servidor Web](SERVIDOR_WEB.md) | HTTPS, certificado, agendamento e SMTP |
| [Segurança do banco](SEGURANCA_BANCO.md) | Backup, restauração e continuidade do NSU |
| [Arquitetura](ARQUITETURA.md) | Componentes e limites operacionais |
| [Histórico](CHANGELOG.md) | Alterações por versão |

## Desenvolvimento

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m compileall -q nfe_consulta
```

A integração contínua executa a suíte em Linux e Windows. Os testes utilizam dados sintéticos e não acessam a SEFAZ real nem enviam e-mails reais. A release é publicada somente após os testes dos dois sistemas passarem.

Para montar o pacote localmente:

```bash
python scripts/package_release.py
```

O empacotador inclui apenas código, recursos estáticos, lançadores e documentação. Pastas operacionais são criadas vazias, sem bancos, credenciais, certificados, logs ou planilhas.

### Downloads recentes

A aba **Downloads** guarda cópias dos relatórios Excel/CSV e dos XMLs baixados por **24 horas após a geração**. Cada arquivo mostra a quantidade de documentos processados, o período do relatório, a geração e a expiração em horário de Brasília. Baixar novamente não renova o prazo. As cópias ficam em `dados/downloads`, fora do banco fiscal, e são removidas automaticamente. A quantidade representa notas distintas nos relatórios; os registros de importação ficam disponíveis apenas no Admin. O período usa o filtro informado ou as datas de emissão dos XMLs / eventos das manifestações; sem datas, aparece “Não informado”.
