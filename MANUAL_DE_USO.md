# Manual de uso — v2.5.0

## Acesso

Abra o endereço do aplicativo. Consulta, Status, Emissão e exportações são públicos na rede. Ao abrir **Admin**, informe uma conta administrativa. A importação e as configurações exigem sessão válida, mesmo por endereço direto. Use **Sair do Admin** para encerrar a sessão. Operações públicas usam a identidade `usuario-interno`; operações administrativas registram a conta autenticada.

## Consulta

A tela **Consulta** pesquisa o histórico armazenado no banco. Os filtros são data inicial e final do evento, número da NF, chave de acesso e tipo de manifestação. A data final inclui todo o dia informado. Os resultados aparecem em páginas de até 100 registros.

A tabela mostra número e série da nota, emitente, situação de cancelamento, manifestação, data, protocolo, chave, NSU, CT-e e ações. Quando o documento recebido não informa a razão social, o emitente aparece pelo CNPJ extraído da chave.

A ausência de registro significa que o evento não foi localizado no histórico disponível. A consulta não verifica a situação atual da NF-e na SEFAZ.

## Exportar Excel

Use **Exportar Excel** após a consulta. A planilha inclui todos os registros dos mesmos filtros, inclusive os que estão em outras páginas. Chaves, protocolos e NSUs são preservados como texto.

Colunas: Número NF, Série, Chave NF-e, Código, Manifestação, Data do evento, Protocolo, NSU, Recebido no banco (UTC), Emitente, Situação e CT-e vinculado. Para consultas acima de 200 mil eventos, refine os filtros antes de exportar.

## Consulta por arquivo

Selecione um TXT com uma chave de 44 dígitos por linha e use **Gerar Excel por chaves**. O arquivo serve para recortar o histórico do banco; não dispara uma consulta pontual à SEFAZ. O limite é de 10 mil chaves e 2 MB por upload.

## Emissão — XMLs e cancelamentos

1. Baixe o lote mensal de XMLs completos no Synchro.
2. Abra **Admin → Importar XML**, selecione o ZIP ou vários XMLs e clique **Importar dados**.
3. Confira as quantidades importadas, duplicadas e recusadas. **Baixar registro do lote** lista o resultado por arquivo.
4. Consulte **Notas emitidas**, **Itens e impostos** ou **PIS/COFINS retidos**. Os dados dos meses anteriores permanecem no banco. Chaves repetidas preservam os dados da primeira importação, mesmo que o XML reenviado tenha conteúdo diferente.

O período do leitor filtra a **emissão da nota**. A consulta de manifestações continua filtrando a data do evento. A busca localiza número, chave e destinatário; nos itens também pesquisa o conteúdo fiscal e o produto. Os resultados têm 100 linhas por página. O Excel reúne Notas, Itens e Retencoes com os mesmos filtros e todas as páginas. O CSV exporta o relatório selecionado. Cada relatório tem limite de 100 mil linhas na exportação.

Na tela **Consulta**, uma nota importada permite **Ver itens**. Na aba Emissão, cada nota oferece Itens e Manifestações. Notas sem evento de manifestação também podem ser importadas. O app não oferece download do XML original; use o Synchro.

Não há chamadas à SEFAZ na importação, leitura ou exportação de relatórios; o certificado não é necessário. A importação não altera NSU, cooldown, agendamento ou manifestações.

Limites: 100 MiB de arquivos por envio, 250 MiB descompactados no lote, 5.000 entradas por ZIP/documentos no lote e 8 MiB por XML. ZIPs podem ter subpastas, mas não devem ser protegidos por senha. Arquivos que não sejam XML, eventos sem cancelamento homologado, resumos e documentos de outro emitente são recusados com registro. Se houver ZIP estruturalmente inválido ou excesso de limite do lote, nenhuma nova nota daquele envio é gravada; divida ou corrija o lote. Erros em XMLs individuais permitem importar os demais arquivos válidos.

São aceitas NF-e modelo 55 completas, com ou sem envelope nfeProc, emitidas pelo CNPJ configurado no aplicativo. O leitor verifica a estrutura mínima e a correspondência da chave/emitente/número/série; não valida assinatura digital, schema fiscal completo nem autorização atual. Use o XML original autorizado obtido no sistema emissor.

Os dados extraídos para consulta e relatórios ficam no banco fiscal configurado; bancos SQLCipher protegem os novos dados com a mesma senha. O banco cresce conforme as importações: inclua-o nos backups e mantenha espaço livre. O arquivo recebido é usado temporariamente durante a importação e removido ao terminar.

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

A rotina executa às **22:00 e 01:00 (Brasília)**, todos os dias. Usa o mesmo banco, certificado, cursor e cooldown da rotina manual. O aplicativo precisa permanecer em execução.

Uma janela concluída não é repetida após reiniciar. Falhas e distribuições parciais são retomadas na próxima janela, respeitando o bloqueio vigente. A rejeição 656 registra uma pausa; não altere o NSU para tentar eliminar esse bloqueio.

## Alertas de Operação não Realizada

Em **Admin → Alertas por e-mail**, cadastre até 20 endereços, separados por linha ou vírgula. Novos eventos **210240** geram avisos para os destinatários cadastrados. Reprocessar um evento já gravado não cria uma nova mensagem.

Os envios dependem da configuração SMTP do servidor. Falhas temporárias mantêm os avisos na fila. Após corrigir o SMTP, use **Tentar enviar pendentes**; isso não refaz a sincronização da SEFAZ. Remover um destinatário cancela seus avisos ainda pendentes.

Uma interrupção após a aceitação pelo SMTP e antes da confirmação no banco pode provocar um segundo envio. A entrega efetiva também depende das regras do servidor de e-mail.

Na consulta, digite `01052026` para visualizar `01/05/2026` enquanto escreve. Informar apenas `01/02` completa o ano atual de Brasília ao sair do campo ou consultar. Datas inexistentes são recusadas.

A sincronização manual exige marcação da confirmação e confirmação final. Repetir o envio ou alterar o botão no navegador não remove o cooldown do servidor.

## Downloads

Abra **Downloads** para baixar novamente os arquivos gerados nas últimas 24 horas. A tabela informa os documentos processados, o período, a data de geração e a expiração. O prazo é contado a partir da geração e não muda quando o arquivo é baixado novamente. Após expirar, gere um novo relatório. Os registros de importação exigem acesso ao Admin. A exclusão das cópias não remove as notas do banco.

Ao solicitar EXCEL ou CSV, você é direcionado a Downloads. A solicitação aparece imediatamente como **Na fila** ou **Gerando arquivo**, com uma barra de atividade. A tabela se atualiza automaticamente e libera o botão de baixar quando o arquivo está pronto. Você pode mudar de página sem cancelar a geração. A geração em andamento depende do processo do servidor; reiniciar o servidor interrompe as tarefas pendentes.

O sininho ao lado do tema também acompanha **Na fila** e **Gerando arquivo** com uma barra de atividade, em qualquer aba. Quando termina, mostra **Processamento concluído** ou **Erro na geração** após uma solicitação de arquivo. Os avisos ficam neste navegador por até 24 horas, limitados aos 20 mais recentes. Abra o sininho para marcar os avisos como lidos ou use **Limpar** para removê-los.

Ao baixar pela aba Downloads, a barra mostra a porcentagem do arquivo recebida pelo navegador. Quando a transferência termina, ela chega a **100%** e o navegador inicia o salvamento. Se a conexão for interrompida, aparece **Erro no download** e você pode tentar novamente.

## CT-e vinculado

Nas abas Consulta e Emissão, abra o indicador **CT-e vinculado** para ver os conhecimentos associados à nota. O indicador **CT-e cancelado** aparece quando todos os vínculos apresentados estão cancelados. Número, chave e transportadora aparecem somente quando recebidos no evento. Se houver somente um resumo, aparece **Vínculo identificado** ou um cancelamento sem chave; esse cancelamento não é atribuído automaticamente a outro conhecimento. O Excel/CSV também inclui esses dados.

As informações chegam pela sincronização habitual. Depois de atualizar e reiniciar o aplicativo, aguarde a próxima sincronização permitida. Eventos ignorados por versões anteriores não são recuperados automaticamente. **Não localizado** indica ausência de vínculo no banco local, não ausência definitiva de CT-e na SEFAZ.

O Admin aceita XMLs completos de NF-e e XMLs de cancelamento homologado, individualmente ou no ZIP. O evento pode chegar antes da nota. Cancelamentos são ligados pela chave de acesso, preservam os dados do evento e aparecem na coluna **Situação** da Consulta, Emissão, itens, retenções e novos relatórios Excel/CSV, inclusive na consulta por TXT. Reenviar a nota não remove o cancelamento. Um pedido sem retorno, rejeitado, não vinculado ou de homologação não altera a situação. Cancelamentos já recebidos via NSU usam a mesma informação.

A situação mostra **Autorizada** ou **Cancelada**, conforme os registros do banco local. Um cancelamento registrado tem prioridade. Se o arquivo contém apenas a nota autorizada e não traz o cancelamento, importe também o XML do evento. Em buscas por chave ou número, a Consulta mostra o cancelamento mesmo sem manifestações. A importação não altera o NSU nem faz chamadas à SEFAZ. A classificação não consulta a autorização atual na SEFAZ. Relatórios já gerados são cópias do momento da geração; gere outro para refletir novas importações.

Em **Consulta** e **Emissão**, o filtro **Situação** oferece **Todas**, **Autorizada** e **Cancelada**. Ele combina com datas e busca, permanece na paginação e é aplicado aos arquivos exportados. Em Emissão, a seleção vale para notas, itens e retenções; o Excel aplica a mesma situação a todas as abas. **Limpar** volta a mostrar todas as situações.

### Alteração manual de situação

Em **Admin → Alterar situação de notas**, informe números ou chaves de acesso, uma por linha, e o motivo. **Marcar como cancelada** atualiza a situação local na Consulta, Emissão e nos novos relatórios. São aceitas até 100 notas existentes no banco da empresa; números ambíguos exigem a chave. Se qualquer nota for inválida ou não encontrada, nenhuma nota do pedido é alterada.

**Remover marcação manual** desfaz somente a correção interna. Um cancelamento recebido pelo NSU ou XML continua válido. Reimportações preservam a marcação manual. O histórico no banco registra usuário, motivo, ação e data; os dados dos eventos da SEFAZ são preservados. Essa função não transmite um evento à SEFAZ. Arquivos já gerados permanecem com a situação existente na geração; gere um novo relatório após a alteração.

### Filtro e tela de itens

Na Emissão, **Item** pesquisa descrição, código ou NCM dos produtos. Em notas e retenções, mostra os documentos que contêm o produto; no relatório de itens, mostra apenas as linhas correspondentes. O filtro combina com datas, busca e situação e acompanha as exportações.

O ícone **Itens** de uma nota abre uma tela própria, com os dados da nota, filtro de produtos e exportação dos seus itens. **Voltar** retorna à Emissão com os filtros e a página anteriores, restaurando a posição de rolagem quando o navegador permite armazenamento de sessão.

O ícone **Manifestações** na Emissão abre uma tela da nota com os eventos existentes no banco local, filtros por data e manifestação e exportação para Excel. **Voltar** mantém os filtros, a página e a posição da lista. Se não houver eventos, a tela informa que nenhum registro foi encontrado.


### Convivência com a captura do Qive

As consultas externas deste aplicativo são permitidas diariamente das 22h às
04h, no horário de Brasília (UTC-3). A sincronização automática mantém os
horários de 22h e 01h nos dias configurados. Recuperações e retentativas também
respeitam a janela, inclusive entre lotes. Uma requisição já iniciada pode terminar
após o fechamento; a próxima não é enviada. Consultas locais e exportações seguem
disponíveis. O limite é verificado no servidor, independentemente do botão.

Ative a rotina em produção após o Qive confirmar o ajuste. A janela foi
escolhida para separar o app da janela de 08h às 18h solicitada ao suporte do Qive. Isso não garante, por si só, que a SEFAZ aceitará cursores
independentes: acompanhe os retornos e confirme a configuração ativa com o Qive.

O ultNSU de uma rejeição 656 fica registrado como divergência para conferência e
recuperação. Ele não substitui o cursor de distribuição. A próxima distribuição
parte do último cursor gravado com sucesso; os documentos de lacunas continuam
sendo recuperados via consNSU, respeitando o limite horário e o bloqueio.
As respostas recebidas são preservadas antes do processamento e os documentos e
cursor são gravados na mesma transação. Esta atualização não restaura cursores
antigos nem elimina pendências de bancos existentes.


### Primeiro teste com as janelas separadas

Antes de ativar a rotina, confirme com o Qive que as consultas e novas tentativas
foram limitadas às 08h–18h de Brasília. Mantenha o computador e o aplicativo
ligados durante a noite. O app dispara às 22h e 01h; fora das 22h–04h, consultas
externas manuais, recuperação e retentativas ficam bloqueadas. A consulta ao
banco local pode ser usada durante o dia.

No Status, abra **Abrir logs** para acompanhar a execução. Erros novos mostram a
etapa (distribuição ou recuperação), o código da SEFAZ quando recebido, o NSU
inicial, o solicitado, o informado pela SEFAZ e o efetivamente salvo. Também
mostram os lotes gravados, respostas pendentes, duração, próxima tentativa
permitida e uma referência que reúne os registros da mesma execução no arquivo
`logs/web_audit.log`. Horários novos de erro são identificados como Brasília;
registros antigos conservam o horário do servidor.

Se ocorrer 656, respeite a pausa e acompanhe as lacunas; não altere o cursor nem
apague pendências para forçar o teste. Se houver falha de gravação, a resposta
preservada permanece para processamento posterior. Falhas de certificado,
configuração ou comunicação são registradas e a rotina automática aguarda a
próxima janela de disparo, evitando repetir o mesmo erro a cada minuto.

Depois da primeira noite, confira o NSU salvo, os documentos recuperados e os
retornos da SEFAZ. Se a 656 persistir mesmo com os horários separados, use a
referência e os NSUs do log para retomar a análise com o Qive.


### Versão de teste: recuperação consNSU pausada

Esta versão inicia com `NFE_RECOVERY_ENABLED=0`. Consultas manuais e automáticas
via aplicativo web usam distNSU, mantendo a fila e as respostas de recuperação
consNSU salvas no banco. O agendador não usa essa fila pausada para antecipar uma
consulta. A janela das 22h–04h, os disparos às 22h/01h e a pausa após 656 permanecem.
O Status indica que a recuperação está pausada.

Após avaliar o teste, para retomar a recuperação, feche o app e execute no Prompt
de Comando, dentro da pasta da instalação:

```bat
set NFE_RECOVERY_ENABLED=1
INICIAR_WEB.cmd
```

Para manter a recuperação pausada, use `NFE_RECOVERY_ENABLED=0`. As pendências não
são apagadas ao alternar essa configuração. Antes do teste noturno, confirme que
o Qive aplicou a janela combinada; atualizar o código não confirma o ajuste deles.


### Armazenamento de dados sem cópias permanentes dos XMLs

Novas importações preservam cabeçalhos, itens, impostos, retenções, cancelamentos
homologados e os demais dados extraídos usados pelas consultas e relatórios.
Documentos distribuídos pela SEFAZ deixam registros de NSU, schema e classificação,
as manifestações e os vínculos com CT-e. O XML original não fica guardado depois
de o processamento terminar; consulte-o no Synchro.

Uma resposta SEFAZ recebida permanece temporariamente no banco até os dados e o
controle de processamento serem gravados na mesma transação. Se a gravação falhar,
a resposta permanece pendente para nova tentativa. Respostas consNSU já tratadas
são limpas ao confirmar o recebimento, a indisponibilidade ou a rejeição 656.

A opção de baixar XML e sua rota foram retiradas. A aba Downloads continua com
Excel, CSV e registros dos lotes; cópias antigas de XML não são disponibilizadas.

Esta mudança não apaga retroativamente os XMLs existentes, não altera o cursor,
não remove pendências e não compacta o banco. Os 161 MB atuais podem permanecer;
o benefício imediato é evitar o crescimento por novas cópias de XML. Uma limpeza
do histórico existente exige uma manutenção separada. Colunas legadas de XML
continuam no schema por compatibilidade, sem conteúdo em novos documentos.

Dados já extraídos podem gerar novos relatórios. Para extrair futuramente um campo
que não foi armazenado, será necessário obter novamente o XML na origem; o app
não terá uma cópia permanente para reprocessamento.
