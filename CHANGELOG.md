# Histórico de versões

## 2.4.0 — 2026-10-05

- Login individual obrigatório para consultar qualquer dado fiscal, inclusive por links diretos.
- Perfis Consulta, Fiscal e Administrador; cadastro padrão com privilégio mínimo.
- Download de XML e exportações restritos a Fiscal/Administrador; importação, configuração e sincronização permanecem administrativas.
- Gestão de perfis e revogação de sessões ao alterar perfil, senha ou estado da conta.
- Migração preserva administradores e senhas existentes e encerra sessões anteriores.
- Proteção transacional do último administrador ativo; CSRF vinculado à sessão de todos os perfis.
- Auditoria de acessos com usuário e perfil; healthcheck sem dados sobre o banco.

## 2.3.0 — 2026-10-05

- Leitor XML de saída integrado com importação administrativa de XMLs ou ZIPs mensais.
- Arquivo cumulativo no banco fiscal, preservação do original e deduplicação pela chave.
- Consulta de notas, itens/impostos e retenções, filtros pela emissão e exportações Excel/CSV.
- Download do XML e acesso aos itens diretamente na consulta de manifestações.
- Histórico de importações e registro por arquivo; XMLs protegidos pelo SQLCipher quando o banco é criptografado.
- Limites de upload, ZIP e exportação, bloqueio de DTD/entidades e proteção contra fórmulas em planilhas.

## 2.2.2 — 2026-10-05

- Agendamento automático fixo às 08:00 e 15:00 de Brasília; removida a janela de meia-noite.
- Sincronização manual com confirmação explícita validada no servidor, confirmação final e prevenção de envio repetido.
- Cooldown do servidor fixado em 60 minutos, inclusive em instalações com configuração antiga.
- Máscara das datas durante a digitação e preenchimento do ano atual ao sair do campo ou consultar.

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
