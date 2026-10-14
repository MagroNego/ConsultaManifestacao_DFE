# AtlasDFE 2.5.1

Sincronização automática a cada hora durante a janela noturna: **22h, 23h, 00h, 01h, 02h e 03h de Brasília**. Às 04h a janela fecha; não há novo disparo nesse horário.

Cooldowns e pausas da SEFAZ continuam prevalecendo sobre o agendamento. Uma tentativa bloqueada aguarda a liberação; não força uma consulta para gerar logs. A trava evita execuções simultâneas e reinícios recuperam apenas o disparo mais recente pendente.

Mantém a identidade AtlasDFE, os dados dos relatórios sem novos XMLs permanentes e a recuperação consNSU pausada. Os dados e XMLs históricos existentes são preservados.

Para atualizar, pare o app, faça backup do banco e da configuração, atualize os arquivos e reinicie. Confirme a janela 08h–18h aplicada no Qive antes do teste. O computador e o processo do app precisam permanecer ativos.
