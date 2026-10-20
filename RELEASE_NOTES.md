# AtlasDFE 2.6.0

## Escopo desta revisão

Documentação da base da main em 19/10/2026, com preparação de login corporativo em 20/10/2026. A versão declarada permanece 2.6.0, mas o ZIP publicado em 16/10/2026 não contém todas as alterações posteriores. Identifique a instalação pelo commit. O workflow não substitui uma release existente.

## Comportamento atual

- Acesso sem login local; todos os acessos têm permissão administrativa. O TI controla o acesso pela infraestrutura. Contas antigas permanecem preservadas no modo legado opcional.
- Sincronização dentro da janela **22h–04h, Brasília**. Agenda padrão às 22h, 23h, 00h, 01h, 02h e 03h; ativação, dias e horários configuráveis no Admin. Cooldown, pausas e trava continuam obrigatórios.
- Recuperação `consNSU` desabilitada por padrão; pendências preservadas. O cursor de distribuição avança somente após processamento confirmado.
- Alertas de Operação não Realizada (`210240`), remetente SMTP configurável e botão de envio de teste.
- Importação de XMLs/ZIPs com subpastas, consultas por chaves ou NOTAS.TXT e relatórios Excel/CSV.
- Cancelamento cooperativo de exportações. No modo padrão, a identidade administrativa compartilhada permite cancelar qualquer solicitação. A serialização final do Excel pode concluir antes da limpeza.
- Relatórios temporários por 24 horas. Logs de sincronização descartados após 30 dias, sujeitos também à rotação por tamanho; dados fiscais permanecem no banco.
- Novos XMLs não são arquivados permanentemente. Respostas pendentes são preservadas até processamento; XMLs legados não são apagados automaticamente.

O modo corporativo opcional está preparado para um gateway autenticado do TI, com autorização por grupos; permanece desativado até homologação. Veja o [contrato de integração](SERVIDOR_WEB.md#preparação-para-login-corporativo).

## Validação e limites

Os registros operacionais de 15 e 16/10 mostram distribuição concluída e cursores atualizados nos trechos fornecidos. O operador confirmou a entrega de e-mail na instalação. Esses resultados são históricos; não comprovam a configuração interna do Qive nem todos os cenários de convivência.

A CI está configurada para testes sintéticos em Windows e Linux. Certificado, comunicação SEFAZ e entrega SMTP dependem da instalação. O aplicativo não transmite manifestações/cancelamentos nem consulta a situação fiscal atual de cada nota. Cancelamentos de emissão própria exigem fonte adicional, conforme [Distribuição DF-e e Qive](DISTRIBUICAO_DFE_QIVE.md#cancelamentos-e-papel-do-cnpj).

## Atualização

Pare o processo, faça backup consistente e registre o commit instalado. Atualize código e dependências, preserve configuração e certificado e valide o banco antes de reativar a agenda. Uma agenda salva prevalece sobre `NFE_AUTO_SYNC_ENABLED`; siga o procedimento de [restauração](SEGURANCA_BANCO.md#restauração) para impedir disparos durante a conferência.

Consulte [Instalação](MANUAL_DE_INSTALACAO.md), [Servidor](SERVIDOR_WEB.md) e [Histórico](CHANGELOG.md).
