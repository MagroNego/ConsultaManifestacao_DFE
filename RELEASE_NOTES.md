# Consulta de Manifestação NF-e v2.2.2

- Automático às 08:00 e 15:00, horário de Brasília. Não há disparo à meia-noite.
- Atualização manual exige login, marcação da confirmação e confirmação final; envios repetidos são bloqueados.
- Cooldown do servidor fixado em 60 minutos. Configurações antigas de intervalo ou cooldown não alteram a rotina.
- Datas: 01052026 vira 01/05/2026 durante a digitação; 01/02 recebe o ano atual ao sair do campo ou consultar.
- Servidor valida confirmação, datas, cooldown e trava compartilhada com o agendamento.

## Atualização

Pare o app, faça backup, substitua código e lançadores e execute INSTALAR.cmd. Preserve dados, secrets, banco, logs e certificado; reinicie com INICIAR_WEB.cmd.

Bloqueios já persistidos são preservados até expirar. Depois de reiniciar, recupera apenas a janela mais recente do dia atual. Antes das 08:00, aguarda a primeira janela. Falhas ou resultados parciais são retomados na próxima janela.

O pacote é publicado após os testes de Linux e Windows passarem.
