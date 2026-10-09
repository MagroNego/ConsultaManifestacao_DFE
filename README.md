# NexusDFE

**NexusDFE** é uma aplicação Web para consultar manifestações de NF-e, exportar relatórios Excel e sincronizar o histórico com o serviço **NFeDistribuicaoDFe** do Ambiente Nacional da NF-e.

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

Consulta, Status e exportações usam o banco local e não fazem chamadas à SEFAZ. A aplicação consulta manifestações e reconhece cancelamentos de NF-e registrados no banco por NSU ou pela importação de XML homologado. Não emite eventos de manifestação ou cancelamento.

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

A conclusão de cada janela é registrada no banco para evitar repetição após reiniciar. Se o servidor voltar depois de um horário programado, recupera apenas a janela mais recente ainda não concluída. Quando a tentativa automática encontra cooldown ou rejeição 656, ela é reagendada para o término do bloqueio persistido, inclusive se a rejeição não informar um NSU de recuperação. Por exemplo, uma execução das 08:00 bloqueada até 08:39 retoma às 08:39; uma rejeição às 15:00 com pausa até 16:00 retoma às 16:00. Outras falhas e resultados parciais são retomados na próxima janela, respeitando o cooldown persistente. Após reiniciar, recupera apenas a janela mais recente do dia atual; antes das 08:00, aguarda a primeira janela. A rotina manual e a automática compartilham a mesma trava e o mesmo cursor NSU.

O cooldown padrão é **60 minutos**. A configuração antiga de cooldown é ignorada: o servidor usa 60 minutos. Bloqueios já persistidos são preservados até expirar. A rejeição 656 mantém o cursor dos lotes gravados e registra separadamente um NSU de recuperação quando a SEFAZ informa um número válido maior. Com a rotina automática ativa, a consulta é retomada após a pausa/cooldown, sem esperar a próxima janela diária. A retomada usa esse NSU e mantém o intervalo como **histórico pendente de conferência** no Status: não afirma que os documentos desse intervalo foram importados. Rejeições sem NSU válido não provocam ajuste de cursor.

As respostas de distribuição são preservadas na tabela `respostas_distribuicao` do próprio banco fiscal antes da interpretação. Após falha de leitura/gravação ou reinício, respostas pendentes são processadas antes de nova chamada à SEFAZ. O processamento do lote, o cursor e a confirmação da resposta são gravados na mesma transação. O XML da resposta é removido após processamento confirmado; ficam o horário, o NSU enviado e o resultado. XML inválido permanece pendente para investigação, sem avanço silencioso. A tabela `recuperacoes_nsu` registra divergências e a data de retomada. Esta proteção vale para respostas recebidas a partir desta versão; não recupera respostas perdidas por versões anteriores ou que não chegaram ao servidor.

## Lotes mensais de XML

Abra **Admin → Importar XML** e envie o ZIP baixado do Synchro ou vários XMLs completos. Os documentos ficam arquivados no banco fiscal, preservando os meses anteriores e ignorando chaves repetidas. Consulte por emissão, número, chave ou destinatário; abra itens e retenções e exporte Excel/CSV. Na Consulta, **Baixar XML** aparece quando a chave tem arquivo importado.

O leitor foi integrado a partir de [Leitor_XML_Saida](https://github.com/MagroNego/Leitor_XML_Saida). Aceita NF-e modelo 55 emitidas pelo CNPJ do aplicativo. A importação é local, sem certificado e sem chamadas à SEFAZ. Faça backup do banco fiscal para preservar também os XMLs; SQLCipher protege os novos dados quando habilitado. Veja limites e detalhes no [manual de uso](MANUAL_DE_USO.md).

## Administração e segurança

Consulta, Status, Emissão e exportações não exigem login. **Admin** exige uma conta administrativa: importação de XML, sincronização manual, configuração e histórico são protegidos no servidor, inclusive por URLs diretas. `CONFIGURAR_ADMIN.cmd` cria ou redefine a conta escolhida, preserva as demais e faz backup do banco de contas antes de alterar uma instalação existente.

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

### CT-e vinculado à NF-e

Consulta e Emissão exibem os vínculos de CT-e recebidos na distribuição da NF-e, com situação autorizado/cancelado e, quando disponíveis, número, chave e transportadora. As exportações Excel/CSV e a consulta por TXT incluem a coluna **CT-e vinculado**. Uma nota pode ter vários conhecimentos; cancelar um CT-e não cancela os demais nem a NF-e. Quando a SEFAZ envia somente um resumo, aparece **Vínculo identificado**, sem inventar uma chave ou correlacionar um cancelamento sem chave com outro CT-e.

Os eventos 610600/610601 ficam na tabela `eventos_cte` do mesmo banco fiscal, separados das manifestações do destinatário. A migração ocorre na próxima abertura do banco para gravação/sincronização; a consulta de bancos antigos continua funcionando. A sincronização passa a guardar os eventos recebidos a partir desta versão. Eventos que versões anteriores ignoraram não são recuperados automaticamente: o aplicativo não reinicia o NSU, não altera o agendamento/cooldown e não consulta a SEFAZ ao abrir uma tabela. **Não localizado** significa que o banco local não recebeu esse vínculo, e não garante a inexistência de CT-e. Esta funcionalidade não importa nem baixa o XML completo do CT-e.

Referência: [Boletim Técnico 2012/001 — CT-e Autorizado e Cancelado](https://hom.nfe.fazenda.gov.br/arearestrita/inicial/exibirArquivo.aspx?conteudo=Jk9wIgAv0nI%3D).

A aba **Emissão** reúne notas, itens e retenções. Importar um cancelamento homologado no Admin marca a chave como **Cancelada** na Consulta, Emissão e nos novos relatórios. O evento pode ser importado antes da nota; duplicatas não desfazem o cancelamento. A situação exibida usa a regra local: **Cancelada** quando há cancelamento registrado e **Autorizada** nos demais casos. Essa classificação não realiza uma consulta atual à SEFAZ.
