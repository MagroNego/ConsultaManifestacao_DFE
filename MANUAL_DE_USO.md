# Operação do AtlasDFE

## Acesso e perfis

Todas as telas de dados exigem login. **Criar minha conta** exige e-mail único, usuário e senha de pelo menos 12 caracteres; o cadastro libera imediatamente o perfil comum. É possível entrar pelo e-mail ou pelo usuário. O vínculo cadastral não confirma a propriedade da caixa postal e não envia mensagem de verificação. A criação de conta é acessível a quem alcançar a aplicação na rede.

| Perfil | Permissões |
| --- | --- |
| Usuário comum | Consulta, Status, Emissão, relatórios e Downloads |
| Administrador | Permissões comuns, importação, sincronização manual, configuração e gestão de contas |

Em **Admin → Gerenciar usuários**, o administrador pode cadastrar, alterar perfil, redefinir senha, ativar, desativar ou excluir contas. Mudanças de acesso revogam sessões. A exclusão exige confirmação e preserva dados fiscais e auditoria. O último administrador ativo é protegido. Contas antigas continuam entrando pelo usuário; o administrador pode vincular um e-mail em Gerenciar usuários. Alterar o endereço encerra as sessões da conta. O e-mail de acesso não é adicionado automaticamente aos destinatários dos alertas.

Senhas atuais não são recuperáveis: ficam armazenadas como hash. Nos campos de senha inicial e nova senha, Mostrar/Ocultar permite conferir somente o valor digitado antes de salvar.

## Consulta de manifestações

Filtre por data do evento, número da nota, chave, manifestação e situação. A data final inclui o dia inteiro. As páginas mostram até 100 registros. Emitente sem nome disponível é identificado pelo CNPJ extraído da chave.

**Exportar Excel** inclui todas as páginas dos filtros aplicados, até 200 mil eventos. Chaves, protocolos e NSUs são texto. A consulta por TXT oferece **CHAVES.txt** (uma chave de 44 dígitos por linha) e **notas.txt** (um número de NF de 1 a 9 dígitos por linha). Ambas usam exclusivamente o histórico local, com limite de 10 mil entradas e 2 MB. O ícone de interrogação abre o tutorial.

Para números, salve um TXT UTF-8, sem cabeçalho, série ou pontuação:

```text
12345
67890
95022
```

Zeros à esquerda são aceitos e duplicatas numéricas são consideradas uma vez. A consulta inclui todas as chaves correspondentes ao número no banco do CNPJ configurado, sem escolher emitente ou série arbitrariamente. A planilha mantém chave/série e inclui **Numeros solicitados**, com contagem das correspondências e números não localizados. Não localizar significa ausência no banco disponível. Notas conhecidas sem manifestações também são incluídas. O relatório recusa resultados com mais de 100 mil notas; reduza a lista nesse caso.

Ausência de evento significa ausência no banco disponível. A tela não consulta a situação atual da NF-e na SEFAZ.

## Emissão e importação

Em **Admin → Importar XML**, envie os XMLs completos ou o ZIP obtido no Synchro. Subpastas relativas de vários meses são percorridas automaticamente, inclusive pastas com horário no nome; não é necessário extrair ou reorganizar os XMLs. O app lê diretamente os membros do ZIP, sem extrair seus caminhos no disco. Caminhos absolutos/de unidade, referências à pasta superior, links simbólicos e dois-pontos no nome final do XML são recusados com motivo específico no registro. Confira importados, duplicados e recusados; o registro do lote fica restrito ao administrador. A importação acumula dados entre meses. Chaves duplicadas preservam a primeira importação.

Aceita NF-e modelo 55 emitida pelo CNPJ configurado, com ou sem envelope `nfeProc`, e cancelamentos homologados compatíveis. Verifica estrutura mínima e correspondência de chave/emitente/número/série; não valida assinatura digital, schema fiscal completo ou autorização atual.

| Limite | Valor |
| --- | --- |
| Arquivo XML | 8 MB |
| Upload | 100 MB |
| Conteúdo expandido | 250 MB |
| Quantidade de arquivos | 5.000 |
| Exportação por relatório | 100.000 linhas |

O período em **Emissão** usa a data de emissão da nota; **Consulta** usa a data do evento. O filtro **Item** pesquisa código, descrição e NCM. Em notas/retenções, seleciona documentos com o item; no relatório de itens, seleciona as linhas correspondentes.

O Excel reúne Notas, Itens e Retencoes, com os filtros e todas as páginas. O CSV exporta a visão selecionada. Os ícones **Itens** e **Manifestações** abrem detalhes da nota; **Voltar** preserva filtros/página e restaura rolagem quando o navegador permitir.

Novos XMLs originais não ficam armazenados permanentemente nem podem ser baixados pelo app. Dados extraídos continuam disponíveis para relatórios; obtenha o original no Synchro. Para extrair futuramente um campo não armazenado, será necessário reobter o XML. Cópias legadas existentes não são removidas automaticamente.

## Situação e CT-e

A situação é calculada pelo banco local: cancelamento recebido ou marcação manual resulta em **Cancelada**; nos demais casos, **Autorizada**. Não é consulta online de autorização. Cancelamento homologado pode chegar antes da nota; reimportar a nota não o desfaz.

Em **Admin → Alterar situação de notas**, informe até 100 números/chaves e o motivo. Números ambíguos exigem chave. Se houver entrada inválida, nenhuma nota do pedido é alterada. **Remover marcação manual** desfaz somente a correção interna, preservando cancelamentos recebidos por XML/NSU. A operação não transmite evento à SEFAZ.

Abra **CT-e vinculado** para ver os conhecimentos recebidos. Número, chave, transportadora e data aparecem somente quando disponíveis. Cada vínculo é exibido em uma linha, com rolagem horizontal quando necessário. **Vínculo identificado** não implica chave conhecida. **CT-e cancelado** indica todos os vínculos apresentados cancelados; não cancela a NF-e. **Não localizado** indica ausência no banco, não inexistência na SEFAZ. Não há download de XML completo de CT-e.

Relatórios já gerados preservam o estado da geração. Gere novamente após importações ou correções.

## Downloads e cancelamento

Os relatórios ficam disponíveis por 24 horas após a geração, em `dados/downloads`, fora do banco fiscal. Repetir o download não renova a validade. A tabela informa documentos processados, período, geração, expiração, tamanho e estado. Nos relatórios, documentos representam notas distintas, não necessariamente linhas.

| Estado/ação | Comportamento |
| --- | --- |
| Na fila | Aguarda vaga de geração |
| Gerando arquivo | Trabalho em segundo plano; progresso sem percentual de conclusão |
| Cancelar solicitação | Remove da fila ou sinaliza interrupção da geração |
| Cancelando | Aguarda término e limpeza do trabalho ativo |
| Pronto | Arquivo disponível para transferência |
| Cancelar transferência | Interrompe o recebimento no navegador; preserva a cópia pronta |

Usuários cancelam suas próprias solicitações; administradores podem cancelar outras. O cancelamento é verificado durante SQL e montagem das linhas. A gravação final do Excel ainda pode concluir seu bloco antes de descartar o resultado. A porcentagem exibida na transferência mede bytes recebidos, não progresso de geração. Tarefas em andamento não sobrevivem ao reinício do servidor; arquivos concluídos permanecem até expirar.

## Status e sincronização

**Status** mostra disponibilidade, última gravação, `ultNSU`, `maxNSU` e próxima tentativa. **Abrir logs** exibe execuções e intervalos. `ultNSU == maxNSU` indica que a distribuição alcançou o limite informado naquele retorno; não garante que toda nota emitida já esteja disponível.

O AtlasDFE consulta externamente das **22:00 até antes de 04:00, Brasília**. Disparos: **22h, 23h, 00h, 01h, 02h e 03h**. Manual, automático e retentativas compartilham banco, certificado, cursor, trava e cooldown. Em **Admin → Disparos automáticos**, marque ou desmarque **Ativar disparos automáticos**, informe os horários separados por vírgula e selecione os dias. Use **Salvar agendamento**. A mudança persiste e vale sem reiniciar. São aceitos até seis horários com intervalo mínimo de 60 minutos, dentro das 22h–04h. Os dias seguem a data civil: 01h de terça pertence à terça. Desativar impede novos disparos e retentativas; uma sincronização já iniciada termina normalmente. A reativação pode retomar a oportunidade mais recente da noite atual, respeitando bloqueios.

O processo precisa permanecer ativo. A rotina manual exige as confirmações exibidas pela interface.

`consNSU` permanece pausado (`NFE_RECOVERY_ENABLED=0`). “Intervalo recuperado” pode refletir documentos anteriores ou recebidos por `distNSU`; verifique as colunas de origem da execução. Intervalos completos não são pendências. A conferência cobre somente os intervalos registrados pelo app.

O histórico de sincronização retém 30 dias, sem excluir notas, manifestações, NSUs ou pendências. Registros antigos podem usar o horário do servidor; registros identificados como Brasília devem ser lidos nesse fuso.

Regras detalhadas, atendimento Qive e tratamento de 656: [Distribuição DF-e e Qive](DISTRIBUICAO_DFE_QIVE.md).

## E-mail

Em **Admin → Alertas por e-mail**, configure remetente/usuário SMTP e até 20 destinatários. Os avisos automáticos são somente para novos eventos **Operação não Realizada (`210240`)** adicionados ao banco, mesmo quando a data do evento é antiga. Ciência da Operação não gera alerta. Reprocessar evento já registrado não cria outro aviso.

**Enviar e-mail de teste** envia mensagem sintética aos destinatários salvos, sem consultar a SEFAZ. Aguarde um minuto entre testes. Aceitação SMTP não confirma entrega; verifique entrada e spam.

**Tentar enviar pendentes** reprocessa a fila de e-mail, sem repetir sincronização. Falhas temporárias permanecem pendentes; destinatário removido encerra avisos correspondentes. Uma interrupção entre aceitação SMTP e confirmação local pode duplicar o envio.

Remetente e usuário salvos na interface valem nos próximos envios sem reiniciar. Servidor, porta e segurança são variáveis do processo; sua alteração exige reinício. Configuração técnica: [Servidor Web](SERVIDOR_WEB.md).

## Diagnóstico

| Ocorrência | Procedimento |
| --- | --- |
| Token inválido | Atualizar a página, entrar novamente e repetir a ação |
| Intervalo ainda ativo | Aguardar a próxima tentativa indicada; não reiniciar para contornar |
| Rejeição 656 | Preservar cursor e logs, respeitar pausa e conferir janelas/instâncias |
| Resposta pendente | Verificar detalhe da falha; não apagar resposta ou avançar NSU |
| SMTP pendente | Conferir servidor, autenticação, destinatários e detalhe do erro |
| Relatório não reflete alteração | Gerar novo arquivo com os filtros necessários |
| Geração perdida após reinício | Solicitar novamente; tarefas são mantidas em memória |
