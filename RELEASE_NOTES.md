# Consulta de Manifestação NF-e v2.2.1

- Cooldown padrão reduzido para 60 minutos.
- Checagem no servidor e reserva atômica no banco compartilhadas pela atualização manual e automática.
- Tentativas durante cooldown ou pausa 656 são recusadas antes de consultar a SEFAZ, mesmo com o botão alterado no navegador.
- Tentativas recusadas não prolongam a janela de bloqueio.
- Agendamento preservado: 00:00, 08:00 e 16:00, horário de Brasília.

## Atualização

Pare o app, faça backup, substitua o código e lançadores e execute INSTALAR.cmd. Preserve dados, secrets, banco, logs e certificado.

Se NFE_SEFAZ_COOLDOWN_MINUTES estiver configurado como 120 no ambiente do servidor, altere para 60 e reinicie o app. Sem essa variável, o padrão passa a ser 60. Janelas já persistidas mantêm sua validade até expirar; a atualização não apaga pausas existentes.

O pacote é publicado após os testes de Linux e Windows passarem.
