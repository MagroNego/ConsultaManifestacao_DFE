# Manual de uso — v2.2.0

## Consulta

A tela **Consulta** pesquisa o histórico armazenado no banco. Os filtros são data inicial e final do evento, número da NF, chave de acesso e tipo de manifestação. A data final inclui todo o dia informado. Os resultados aparecem em páginas de até 100 registros.

A tabela mostra número e série da nota, emitente, manifestação, data, protocolo, chave, NSU e recebimento no banco. Quando o documento recebido não informa a razão social, o emitente aparece pelo CNPJ extraído da chave.

A ausência de registro significa que o evento não foi localizado no histórico disponível. A consulta não verifica a situação atual da NF-e na SEFAZ.

## Exportar Excel

Use **Exportar Excel** após a consulta. A planilha inclui todos os registros dos mesmos filtros, inclusive os que estão em outras páginas. Chaves, protocolos e NSUs são preservados como texto.

Colunas: Número NF, Série, Chave NF-e, Código, Manifestação, Data do evento, Protocolo, NSU, Recebido no banco (UTC) e Emitente. Para consultas acima de 200 mil eventos, refine os filtros antes de exportar.

## Consulta por arquivo

Selecione um TXT com uma chave de 44 dígitos por linha e use **Gerar Excel por chaves**. O arquivo serve para recortar o histórico do banco; não dispara uma consulta pontual à SEFAZ. O limite é de 10 mil chaves e 2 MB por upload.

## Status

Apresenta última gravação, `ultNSU`, `maxNSU`, disponibilidade da sincronização e as últimas dez execuções. `ultNSU` é o cursor local; `maxNSU` é o limite informado no retorno recebido.

**Completo** indica que a última distribuição alcançou o limite disponível. **Parcial** indica que ainda há distribuição a processar. O bloqueio e a próxima tentativa permitida são mostrados quando houver cooldown.

## Atualizar

A área exige login administrativo e reúne:

- Configuração do banco e certificado A1.
- Sincronização manual e estado do agendamento automático.
- Contas individuais e troca de senha/desativação.
- Destinatários e fila dos alertas por e-mail.
- Histórico administrativo.

Use **Sair** para encerrar e revogar a sessão. Trocar a senha ou alterar o estado de uma conta também encerra suas sessões. Mantenha ao menos um administrador ativo.

## Sincronização automática

A rotina executa a cada **8 horas**, às **00:00, 08:00 e 16:00 (Brasília)**, todos os dias. Usa o mesmo banco, certificado, cursor e cooldown da rotina manual. O aplicativo precisa permanecer em execução.

Uma janela concluída não é repetida após reiniciar. Falhas e distribuições parciais podem ser retomadas a cada hora, respeitando o bloqueio vigente. A rejeição 656 registra uma pausa; não altere o NSU para tentar eliminar esse bloqueio.

## Alertas de Operação não Realizada

Em **Atualizar → Alertas por e-mail**, cadastre até 20 endereços, separados por linha ou vírgula. Novos eventos **210240** geram avisos para os destinatários cadastrados. Reprocessar um evento já gravado não cria uma nova mensagem.

Os envios dependem da configuração SMTP do servidor. Falhas temporárias mantêm os avisos na fila. Após corrigir o SMTP, use **Tentar enviar pendentes**; isso não refaz a sincronização da SEFAZ. Remover um destinatário cancela seus avisos ainda pendentes.

Uma interrupção após a aceitação pelo SMTP e antes da confirmação no banco pode provocar um segundo envio. A entrega efetiva também depende das regras do servidor de e-mail.
