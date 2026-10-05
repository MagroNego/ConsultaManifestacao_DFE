# Histórico de versões

## 2.2.1 — 2026-10-05

- Cooldown padrão de 60 minutos, validado no servidor para atualização manual e automática.
- Reserva atômica no banco impede duas sincronizações simultâneas de ultrapassarem a checagem.
- Pausa 656 verificada antes do certificado, sem estender o bloqueio por tentativas recusadas.
- Testes de POST direto, agendamento bloqueado e disputa entre conexões.

## 2.2.0 — 2026-09-30

- Sincronização recorrente a cada oito horas, em janelas fixas de Brasília e com estado persistente por janela.
- Contas administrativas individuais e sessões revogadas no logout, troca de senha e alteração de estado da conta.
- Alertas por e-mail para novos eventos de Operação não Realizada, com fila persistente e administração de destinatários.
- Emitente na consulta e no Excel; histórico operacional no Status e histórico administrativo restrito.
- Limites de upload e exportação, controle de tentativas de login e dependências de segurança atualizadas.
- Retirada do filtro e da coluna de cancelamento da consulta e do Excel.
- Retirada do lançador de teste de data única; versão e documentação consolidadas.
- Pacote de instalação com lista explícita de arquivos e checksum SHA-256.

## 2.1.1

- Consulta com filtros e exportação; agendador interno e diagnóstico dos retornos 656.
- Retirada das interfaces CLI e desktop legadas.

## 2.0.1

- Segredos de runtime centralizados e ajustes de configuração e implantação.

## 2.0.0

- Interface Web com administração centralizada e consulta ao histórico local.
