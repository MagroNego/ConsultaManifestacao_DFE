# Revisão técnica — v2.1.1

## Componentes

- `nfe_consulta/web/app.py`: interface Web, acesso público à consulta e login
  administrativo para configuração e sincronização.
- `nfe_consulta/web/consulta_local.py`: filtros, paginação e exportação local.
- `nfe_consulta/web/scheduler.py`: execução automática enquanto o servidor
  estiver em funcionamento, com registro diário no banco.
- `nfe_consulta/sincronizacao.py` e `distribuicao.py`: leitura sequencial de NSU
  e integração com o Ambiente Nacional da NF-e.
- `nfe_consulta/banco.py`: eventos, cursor NSU, pausa por 656 e cooldown.

## Controles

- Banco SQLCipher com senha em `secrets/db-password.txt`.
- Certificado A1 do Windows (`CurrentUser` ou `LocalMachine`) ou PFX/P12
  configurado na aba **Atualizar**; arquivos de segredo não entram no pacote.
- Atualização exige login administrativo, sessão assinada e token CSRF.
- Consulta e exportação não fazem chamadas à SEFAZ.
- Uma sincronização por processo; para SQLite, execute somente um processo.
- Retornos válidos e cursor são gravados em uma transação. O erro 656 registra
  pausa, NSU enviado e, quando informado, o NSU indicado pela SEFAZ, sem
  avançar automaticamente o cursor.
- XML processado com `defusedxml`; limites de tamanho e SQL parametrizado.
- Auditoria em `logs/web_audit.log`, sem senha nem certificado.

## Validação

Os 73 testes automatizados passaram no ambiente de preparação. Consulta,
exportação Excel e sincronização manual foram exercitadas no Windows com o
certificado do usuário em 28/09/2026; a sincronização concluiu com
`ultNSU = maxNSU = 000000000564242`.

A instalação definitiva, permissões do certificado da conta de serviço,
backup/restauração e agendamento automático devem ser validados no servidor
escolhido pela TI. Outros sistemas que consultem o mesmo CNPJ compartilham
as regras de sequência e consumo do serviço de distribuição.
