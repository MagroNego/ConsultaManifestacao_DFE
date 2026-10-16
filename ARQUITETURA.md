# Arquitetura técnica

## Componentes

| Módulo | Responsabilidade |
| --- | --- |
| `web/app.py` | Rotas, middleware, autorização e coordenação |
| `web/auth.py`, `web/admin_accounts.py` | Contas, hash de senha, sessões e CSRF |
| `web/consulta_local.py` | Consultas e filtros locais |
| `web/scheduler.py`, `web/sync_runtime.py` | Agendamento, trava, cooldown e configuração |
| `janela_consulta.py` | Restrição de horário antes das chamadas externas |
| `sincronizacao.py`, `distribuicao.py` | Fluxo distNSU e transporte SOAP/PowerShell |
| `recuperacao_nsu.py` | Recuperação pontual e limite de consultas |
| `banco.py`, `seguranca_banco.py` | Transações e SQLite/SQLCipher |
| `xml_reader.py`, `web/xml_store.py`, `web/xml_routes.py` | Extração, importação e relatórios de emissão |
| `cancelamento.py`, `cte.py` | Situação local e vínculos de CT-e |
| `web/export_queue.py`, `web/export_jobs.py`, `export_control.py` | Fila, execução assíncrona e cancelamento cooperativo |
| `web/downloads.py` | Arquivo temporário de relatórios |
| `web/email_alerts.py` | Configuração SMTP e processamento de notificações |
| `web/audit.py`, `web/sync_history.py` | Auditoria, diagnóstico e retenção operacional |

## Persistência e consistência

O banco fiscal mantém manifestações, dados das notas, cancelamentos, CT-e, estado de distribuição, cooldown, intervalos, agendamento e fila SMTP. `xml_documentos`, `xml_relatorio` e `xml_importacoes` mantêm metadados, hash, dados extraídos e registros de importação. Colunas XML legadas permanecem por compatibilidade; documentos novos não mantêm cópias permanentes do original.

Respostas `distNSU` são persistidas antes do parser. A confirmação de processamento, os dados e o cursor são transacionais. Resposta inválida permanece pendente e impede avanço silencioso. Rejeição 656 preserva cursor e registra pausa/divergência; `nsu_para_consulta()` retorna o cursor local gravado. Respostas `consNSU` também são preservadas durante o processamento e limpas após resultado confirmado.

Importação usa a trava compartilhada com sincronização e não altera cursor. Cancelamentos homologados e marcações administrativas alimentam a situação local; remoção de marcação manual não desfaz evento da SEFAZ. CT-e é armazenado em `eventos_cte`, separado de manifestações. A ausência de vínculo não prova inexistência de conhecimento.

Contas, perfis e sessões ficam em SQLite separado. Senhas usam PBKDF2; tokens de sessão, SHA-256. Alterações de acesso revogam sessões e preservam o último administrador ativo. Cadastro próprio sempre gera perfil comum. Toda rota de dados exige autenticação; rotas administrativas validam perfil no servidor.

## Concorrência e agendamento

A implantação exige um processo/worker. As travas locais não coordenam processos separados. O banco deve permanecer preferencialmente em disco local.

Janela externa: **22:00 inclusive a 04:00 exclusiva, UTC−3**. Disparos: **22, 23, 00, 01, 02 e 03 horas**. O controle em `controle_agendamento_intervalo` evita repetir oportunidade concluída após reinício. Cooldown e pausas persistem no banco. A oportunidade mais recente elegível pode ser retomada; o agendador não reproduz todas as oportunidades perdidas.

`consNSU` inicia desabilitado. Se habilitado com lacunas, a recuperação tem prioridade e consome a execução antes de nova distribuição. Política completa: [Distribuição DF-e e Qive](DISTRIBUICAO_DFE_QIVE.md).

## Relatórios e cancelamento

Trabalho pesado executa em threads; duas exportações simultâneas e 16 aguardando. A interface recebe HTTP 202 e acompanha o estado em memória. Relatórios prontos ficam no filesystem por 24 horas.

O pedido de cancelamento sinaliza um `threading.Event`, propagado por `ContextVar`. Consultas SQL usam progress handler; montagem das linhas verifica o sinal. O worker encerra antes de liberar a vaga. A serialização final do Excel ainda conclui o bloco corrente; o resultado cancelado é descartado. Arquivos publicados não são removidos por cancelamento de geração. Interromper a transferência no navegador preserva a cópia pronta.

## Limites de validação

Importação verifica estrutura mínima e consistência de campos; não valida assinatura XML nem autorização atual na SEFAZ. A situação Autorizada é a classificação local quando não há cancelamento registrado. O app não transmite manifestações ou cancelamentos.

A CI executa testes sintéticos em Windows/Linux. Comunicação real SEFAZ, certificado da instalação, entrega SMTP e convivência com Qive dependem de validação operacional. Aceitação SMTP e confirmação no banco não formam transação única; pode ocorrer duplicidade após interrupção.

O empacotador usa lista explícita de arquivos, sem dados/segredos. A publicação requer CI aprovada e cria ZIP/checksum somente quando a versão ainda não possui release. Código novo na main não substitui ZIP já publicado com a mesma versão.
