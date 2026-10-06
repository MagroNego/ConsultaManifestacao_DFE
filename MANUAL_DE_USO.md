# Manual de uso — v2.4.0

## Acesso

Abra o endereço do aplicativo. Consulta, Status, XML e exportações são públicos na rede. Ao abrir **Admin**, informe uma conta administrativa. A importação e as configurações exigem sessão válida, mesmo por endereço direto. Use **Sair do Admin** para encerrar a sessão. Operações públicas usam a identidade `usuario-interno`; operações administrativas registram a conta autenticada.

## Consulta

A tela **Consulta** pesquisa o histórico armazenado no banco. Os filtros são data inicial e final do evento, número da NF, chave de acesso e tipo de manifestação. A data final inclui todo o dia informado. Os resultados aparecem em páginas de até 100 registros.

A tabela mostra número e série da nota, emitente, manifestação, data, protocolo, chave, NSU e recebimento no banco. Quando o documento recebido não informa a razão social, o emitente aparece pelo CNPJ extraído da chave.

A ausência de registro significa que o evento não foi localizado no histórico disponível. A consulta não verifica a situação atual da NF-e na SEFAZ.

## Exportar Excel

Use **Exportar Excel** após a consulta. A planilha inclui todos os registros dos mesmos filtros, inclusive os que estão em outras páginas. Chaves, protocolos e NSUs são preservados como texto.

Colunas: Número NF, Série, Chave NF-e, Código, Manifestação, Data do evento, Protocolo, NSU, Recebido no banco (UTC) e Emitente. Para consultas acima de 200 mil eventos, refine os filtros antes de exportar.

## Consulta por arquivo

Selecione um TXT com uma chave de 44 dígitos por linha e use **Gerar Excel por chaves**. O arquivo serve para recortar o histórico do banco; não dispara uma consulta pontual à SEFAZ. O limite é de 10 mil chaves e 2 MB por upload.

## XMLs — lotes mensais

1. Baixe o lote mensal de XMLs completos no Synchro.
2. Abra **Admin → Importar XML**, selecione o ZIP ou vários XMLs e clique **Importar e arquivar**.
3. Confira as quantidades importadas, duplicadas e recusadas. **Baixar registro do lote** lista o resultado por arquivo.
4. Consulte **Notas e arquivos**, **Itens e impostos** ou **PIS/COFINS retidos**. Os meses anteriores permanecem no arquivo. Chaves repetidas preservam o primeiro XML, mesmo que o arquivo enviado tenha conteúdo diferente.

O período do leitor filtra a **emissão da nota**. A consulta de manifestações continua filtrando a data do evento. A busca localiza número, chave e destinatário; nos itens também pesquisa o conteúdo fiscal e o produto. Os resultados têm 100 linhas por página. O Excel reúne Notas, Itens e Retencoes com os mesmos filtros e todas as páginas. O CSV exporta o relatório selecionado. Cada relatório tem limite de 100 mil linhas na exportação.

Na tela **Consulta**, uma nota com XML importado mostra **Baixar XML** e **Ver itens**. Na aba XML, cada nota oferece XML, Itens e Manifestações. Notas sem evento de manifestação também podem ser arquivadas. O download entrega os bytes originais do documento.

Não há chamadas à SEFAZ na importação, leitura ou download; o certificado não é necessário. A importação não altera NSU, cooldown, agendamento ou manifestações.

Limites: 100 MiB de arquivos por envio, 250 MiB descompactados no lote, 5.000 entradas por ZIP/documentos no lote e 8 MiB por XML. ZIPs podem ter subpastas, mas não devem ser protegidos por senha. Arquivos que não sejam XML, eventos, resumos e documentos de outro emitente são recusados com registro. Se houver ZIP estruturalmente inválido ou excesso de limite do lote, nenhuma nova nota daquele envio é gravada; divida ou corrija o lote. Erros em XMLs individuais permitem importar os demais arquivos válidos.

São aceitas NF-e modelo 55 completas, com ou sem envelope nfeProc, emitidas pelo CNPJ configurado no aplicativo. O leitor verifica a estrutura mínima e a correspondência da chave/emitente/número/série; não valida assinatura digital, schema fiscal completo nem autorização atual. Use o XML original autorizado obtido no sistema emissor.

Os XMLs e relatórios ficam no banco fiscal configurado; bancos SQLCipher protegem os novos dados com a mesma senha. O banco cresce conforme as importações: inclua-o nos backups e mantenha espaço livre. O arquivo recebido é usado temporariamente durante a importação e removido ao terminar.

## Status

Apresenta última gravação, `ultNSU`, `maxNSU`, disponibilidade da sincronização e as últimas dez execuções. `ultNSU` é o cursor local; `maxNSU` é o limite informado no retorno recebido.

**Completo** indica que a última distribuição alcançou o limite disponível. **Parcial** indica que ainda há distribuição a processar. O bloqueio e a próxima tentativa permitida são mostrados quando houver cooldown.

## Admin

A área exige login administrativo e reúne:

- Configuração do banco e certificado A1.
- Sincronização manual e estado do agendamento automático.
- Importação de XML e ZIP.
- Destinatários e fila dos alertas por e-mail.
- Histórico administrativo.

## Sincronização automática

A rotina executa às **08:00 e 15:00 (Brasília)**, todos os dias. Usa o mesmo banco, certificado, cursor e cooldown da rotina manual. O aplicativo precisa permanecer em execução.

Uma janela concluída não é repetida após reiniciar. Falhas e distribuições parciais são retomadas na próxima janela, respeitando o bloqueio vigente. A rejeição 656 registra uma pausa; não altere o NSU para tentar eliminar esse bloqueio.

## Alertas de Operação não Realizada

Em **Admin → Alertas por e-mail**, cadastre até 20 endereços, separados por linha ou vírgula. Novos eventos **210240** geram avisos para os destinatários cadastrados. Reprocessar um evento já gravado não cria uma nova mensagem.

Os envios dependem da configuração SMTP do servidor. Falhas temporárias mantêm os avisos na fila. Após corrigir o SMTP, use **Tentar enviar pendentes**; isso não refaz a sincronização da SEFAZ. Remover um destinatário cancela seus avisos ainda pendentes.

Uma interrupção após a aceitação pelo SMTP e antes da confirmação no banco pode provocar um segundo envio. A entrega efetiva também depende das regras do servidor de e-mail.

Na consulta, digite `01052026` para visualizar `01/05/2026` enquanto escreve. Informar apenas `01/02` completa o ano atual de Brasília ao sair do campo ou consultar. Datas inexistentes são recusadas.

A sincronização manual exige marcação da confirmação e confirmação final. Repetir o envio ou alterar o botão no navegador não remove o cooldown do servidor.
