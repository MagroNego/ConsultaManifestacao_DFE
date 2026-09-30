# Arquitetura — v2.2.0

## Componentes

| Componente | Responsabilidade |
| --- | --- |
| `web/app.py` | Rotas, autorização, proteção HTTP e coordenação das operações |
| `web/admin_accounts.py` e `web/auth.py` | Contas, hash de senhas, sessões e CSRF |
| `web/consulta_local.py` | Filtros, paginação e leitura do histórico |
| `relatorio_eventos.py` e `xlsx_writer.py` | Relatórios Excel |
| `web/scheduler.py` | Janelas de oito horas, recuperação e estado persistente |
| `web/sync_runtime.py`, `sincronizacao.py` e `distribuicao.py` | Configuração e distribuição por NSU |
| `banco.py` e `seguranca_banco.py` | Persistência SQLite/SQLCipher e transações |
| `web/email_alerts.py` | Destinatários, configuração SMTP e processamento da fila |
| `web/audit.py` e `web/sync_history.py` | Auditoria e histórico operacional |

## Persistência

O banco fiscal guarda manifestações, informações do emitente, cursor, cooldown e fila de e-mails. Contas e sessões administrativas ficam em `dados/admin_accounts.db`, separado do banco fiscal. As sessões armazenam o hash do token e possuem limite de inatividade e duração absoluta.

O agendamento recorrente usa `controle_agendamento_intervalo`: registra a última janela concluída por CNPJ em formato ISO com fuso. O controle anterior de execução diária é preservado para compatibilidade. Um reinício recupera somente a janela mais recente, evitando uma sequência de chamadas para todas as janelas perdidas.

A distribuição grava documentos e cursor em transação. Uma rejeição 656 preserva o cursor local e registra a pausa e os dados operacionais do retorno. Distribuições parciais permanecem elegíveis para retomada após o cooldown.

## Limites operacionais

Execute **um processo com um worker**, pois a trava de sincronização é local ao processo. SQLite/SQLCipher deve ficar preferencialmente no disco local do servidor. Aumentar workers não cria coordenação entre instâncias.

Consulta e exportação são operações locais. O histórico depende dos documentos disponibilizados e recebidos pelo serviço de distribuição. A aplicação não apresenta autorização/cancelamento da NF-e e não transmite manifestações.

A fila SMTP persiste por evento/destinatário. A confirmação do servidor de e-mail e a gravação do envio não são uma transação única; a entrega pode se repetir após uma interrupção nessa etapa.

## Validação e publicação

A suíte automatizada cobre banco, consultas, filtros, exportações, sessões, CSRF, uploads, alertas, bloqueio SEFAZ e agendamento. Os testes não usam certificado de produção nem servidores externos. O fluxo de publicação executa a suíte em Windows e Linux antes de criar a release e anexar o ZIP e seu checksum SHA-256.
