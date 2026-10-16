# AtlasDFE 2.6.0 — versão estável

Consolida a sincronização noturna validada na instalação do usuário, o acesso por contas individuais e os alertas por e-mail.

- Consulta automática às **22h, 23h, 00h, 01h, 02h e 03h**, no horário de Brasília. A janela fecha às 04h. Cooldown, pausas da SEFAZ e trava de execução continuam prevalecendo.
- Login obrigatório para consultas, Status, Emissão, downloads e exportações. Cada pessoa pode criar conta comum com senha própria e acesso imediato. Qualquer pessoa que alcance a tela do app pode se cadastrar, conforme a política escolhida para a instalação.
- Admin exclusivo de administradores: cadastro, redefinição de senha, perfis, ativação/desativação e exclusão confirmada de usuários. Alterações revogam sessões; o último administrador ativo é protegido. Senhas atuais não são exibidas.
- Alertas somente de **Operação não Realizada (210240)**. Remetente e usuário SMTP editáveis; botão de teste sem consultar a SEFAZ ou gerar eventos. A senha de app continua em arquivo local.
- Downloads com botão Cancelar para solicitações próprias na fila ou em geração; administradores podem cancelar outras solicitações. A geração conclui o bloco em andamento antes de liberar recursos e descarta o resultado. Durante a transferência, Cancelar interrompe o recebimento e preserva o arquivo pronto.
- Logs de sincronização com retenção de **30 dias**, preservando auditoria administrativa e dados fiscais. A rotação por tamanho permanece ativa.
- Preserva dados dos relatórios sem novos XMLs permanentes; XMLs históricos existentes não são apagados. O original continua sendo obtido pelo Synchro.

## Recuperação consNSU

Permanece **pausada por padrão**. Intervalos completos não precisam ser reconsultados. A recuperação de uma futura lacuna deve ser validada separadamente, dentro da janela noturna e respeitando as pausas. O cursor distNSU nunca é avançado a partir de uma rejeição.

## Validação

A sincronização noturna teve duas noites com resultado favorável nos registros fornecidos. O usuário confirmou o teste de acesso e a entrega de e-mail na instalação. A suíte automatizada verifica os fluxos com dados sintéticos; a publicação exige aprovação em Windows e Linux. Não foi realizada inspeção visual em navegador nesta preparação.

## Atualização e backup

Pare o app e faça uma cópia consistente do banco fiscal, do banco de contas e da pasta secrets; preserve também o certificado A1 quando externo. O backup completo ainda é manual. Atualize o código e as dependências com INSTALAR.cmd, preserve os caminhos e reinicie com INICIAR_WEB.cmd. Confira login, certificado e cursores no Status. O computador e o processo do app precisam permanecer ativos durante a noite.

## Documentação e correções posteriores na main

A main inclui cancelamento cooperativo durante SQL/montagem das linhas, otimização do Excel e CT-e sem quebra de linha. Essas alterações posteriores não substituem o ZIP 2.6.0 já publicado. A documentação foi revisada em 16/10/2026; configuração e atendimento Qive estão em [Distribuição DF-e e Qive](DISTRIBUICAO_DFE_QIVE.md).
