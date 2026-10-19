# Implantação do servidor

## Processo e rede

Execute **um processo com um worker**, usando banco preferencialmente em disco local. Travas, fila de exportação e tarefas são locais ao processo; múltiplas instâncias não coordenam o consumo SEFAZ. O lançador e `python -m nfe_consulta.web.app` iniciam um worker.

O endereço padrão é `127.0.0.1:8080`. Para acesso interno, use HTTPS por reverse proxy e limite o acesso de rede aos usuários autorizados. A conta do serviço precisa ler certificado/segredos e gravar banco e pastas operacionais. Configure inicialização e reinício pelo gerenciador de serviços do sistema operacional; o pacote não instala automaticamente um serviço.

`GET /healthz` retorna estado básico e versão, sem verificar disponibilidade do banco fiscal. Teste também acesso e Status após implantação.

## Configuração do processo

`WEB_CONFIG.example` não é carregado automaticamente. Defina variáveis no lançador/ambiente do serviço e reinicie após alterações.

| Variável | Padrão/uso |
| --- | --- |
| `NFE_WEB_ENV` | `production` no lançador Windows |
| `NFE_WEB_HOST` / `NFE_WEB_PORT` | `127.0.0.1` / `8080` |
| `NFE_WEB_ROOT_PATH` | Prefixo da aplicação quando publicada em subcaminho pelo proxy |
| `NFE_WEB_FORWARDED_ALLOW_IPS` | `127.0.0.1`; somente proxies confiáveis |
| `NFE_DATABASE_PATH` | Caminho alternativo ao padrão; `secrets/db-path.txt` salvo pelo Admin prevalece |
| `NFE_WEB_LOCAL_AUTH` | `0`: sem login; `1`: modo legado com contas locais |
| `NFE_ADMIN_ACCOUNTS_PATH` | Banco de contas; padrão `dados/admin_accounts.db` |
| `NFE_ADMIN_SESSION_MINUTES` | Inatividade: 30 minutos; faixa aceita 5–480 |
| `NFE_AUTO_SYNC_ENABLED` | `1` no lançador; `0` quando app iniciado diretamente sem configuração |
| `NFE_AUTO_SYNC_WEEKDAYS` | `0,1,2,3,4,5,6`; segunda=0, domingo=6 |
| `NFE_AUTO_SYNC_MAX_LOTES` | 50; faixa 1–500 |
| `NFE_RECOVERY_ENABLED` | `0`; recuperação pontual pausada |
| `NFE_WEB_AUDIT_LOG` | Padrão `logs/web_audit.log` |

A janela é fixa: **22:00 ≤ horário ou horário < 04:00**, Brasília (UTC−3). Disparos padrão às **22h, 23h, 00h, 01h, 02h e 03h**, configuráveis no Admin sem ampliar a janela. A rotina considera os dias configurados e os bloqueios persistidos. Leitura local não depende dessa janela.

`NFE_AUTO_SYNC_ONCE_DATE`, `NFE_AUTO_SYNC_INTERVAL_HOURS`, `NFE_AUTO_SYNC_HOUR`, `NFE_AUTO_SYNC_MINUTE` e `NFE_SEFAZ_COOLDOWN_MINUTES` não substituem o agendamento atual nem o cooldown fixo de 60 minutos. Remova configurações legadas. Detalhes: [Distribuição e Qive](DISTRIBUICAO_DFE_QIVE.md).

## Autenticação e segredos

O acesso padrão dispensa login local, cadastro e senha de administrador (`NFE_WEB_LOCAL_AUTH=0`). Todos os acessos de rede têm permissão administrativa. A autenticação e a autorização devem ser configuradas pelo TI no proxy/infraestrutura. Não são interpretados cabeçalhos de identidade para conceder perfis nesse modo. `NFE_WEB_AUTH_MODE` e cabeçalhos de identidade não habilitam autenticação no modo padrão. As rotas de login, cadastro e gerenciamento de contas retornam 404. A auditoria local usa a identidade compartilhada `acesso-rede`; a identificação individual depende dos registros da infraestrutura. CSRF, limites de upload, trava e janela SEFAZ permanecem ativos.

O modo legado de contas pode ser reativado explicitamente com `NFE_WEB_LOCAL_AUTH=1` e reinício; nesse modo são usados os registros e sessões de `dados/admin_accounts.db`. Não é necessário executar `CONFIGURAR_ADMIN.cmd` no modo padrão. Os dados de contas existentes são preservados sem serem abertos ou alterados no modo sem login.

`INICIAR_WEB.cmd` gera `secrets/web-csrf-secret.txt` quando ausente. Em outros lançadores, forneça esse arquivo ou `NFE_WEB_CSRF_SECRET`, com pelo menos 32 caracteres aleatórios. Preserve o segredo entre reinícios.

| Arquivo padrão | Conteúdo |
| --- | --- |
| `secrets/auto-sync.json` | Estado, horários e dias da sincronização automática salvos pelo Admin |
| `secrets/db-path.txt` | Banco fiscal selecionado |
| `secrets/db-password.txt` | Senha SQLCipher |
| `secrets/cert-path.txt` | Caminho do PFX/P12 |
| `secrets/cert-password.txt` | Senha do certificado |
| `secrets/web-csrf-secret.txt` | Segredo Web persistente |
| `secrets/smtp-password.txt` | Credencial SMTP |
| `secrets/smtp-sender.json` | Remetente e usuário salvos pela interface |
| `secrets/email-recipients.json` | Destinatários cadastrados |

No modo legado de contas, a senha de acesso fica no banco de contas como hash. No modo padrão nenhuma senha administrativa é carregada. `NFE_DATABASE_PASSWORD`, `NFE_CERT_PASSWORD` e `NFE_ADMIN_PASSWORD` não são fontes de senha. Restrinja permissões NTFS/Unix das pastas operacionais.

## Certificado e SEFAZ

Configure PFX/P12 em Admin; a aplicação referencia o arquivo original. Para Windows Certificate Store, use `CurrentUser` ou `LocalMachine`. Sob conta de serviço, conceda leitura da chave privada à identidade que executa o processo.

```text
NFE_CERT_STORE=LocalMachine
NFE_CERT_THUMBPRINT=<impressão digital do certificado>
```

A agenda salva em `secrets/auto-sync.json` prevalece sobre `NFE_AUTO_SYNC_ENABLED` e `NFE_AUTO_SYNC_WEEKDAYS`. O Admin aplica as mudanças sem reiniciar o processo. Desativar não aborta uma sincronização ativa nem desabilita a função manual. Arquivo inválido impede a inicialização com mensagem de configuração, sem retornar silenciosamente aos padrões.

O cliente atual usa PowerShell e o endpoint de produção:

```text
https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx
SOAPAction: http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse
```

O endpoint consta em `nfe_consulta/distribuicao.py`; não há configuração do Gateway Qive na interface. Linux é documentado para uso local/desenvolvimento, não como sincronização real já validada.

## SMTP

```text
NFE_SMTP_HOST=<servidor>
NFE_SMTP_PORT=587
NFE_SMTP_SECURITY=starttls
NFE_SMTP_FROM=<remetente autorizado>
NFE_SMTP_USER=<usuário SMTP>
```

Use `ssl` quando o provedor exigir TLS direto, com a porta correspondente. A senha fica em `secrets/smtp-password.txt`. Remetente/usuário em `secrets/smtp-sender.json` prevalecem sobre o ambiente. Cadastre destinatários pela interface.

Para Gmail com senha de app, remetente/usuário devem corresponder à conta autorizada dessa credencial. Trocar o endereço sem ajustar a autenticação não configura outra conta de envio. O botão de teste valida a aceitação SMTP; a entrega deve ser conferida na caixa destinatária.

A fila `notificacoes_email` persiste no banco fiscal. Somente `210240` gera novos alertas. Reenvio da fila não consulta a SEFAZ. Aceitação SMTP e confirmação no banco não são atômicas; uma interrupção pode duplicar mensagem.

## Exportações, logs e continuidade

- Geração: duas tarefas simultâneas, até 16 em espera, limite de cinco minutos de espera por vaga (não é limite da duração da geração). Fila cheia retorna 429; espera expirada, 503; `Retry-After: 15`.
- Interface solicita geração em segundo plano com HTTP 202 e consulta estado a cada dois segundos. Estados/tarefas em andamento não persistem após reiniciar.
- Cancelamento mantém a vaga até encerrar o trabalho; verifica SQL e linhas. A gravação final do Excel pode terminar antes da limpeza.
- Arquivos prontos ficam em `dados/downloads` por 24 horas. Downloads prontos não entram na fila de geração.
- Auditoria: `logs/web_audit.log` e rotação. Ações de sincronização são descartadas após 30 dias; a rotação por tamanho pode removê-las antes. Arquivos de até 5 MiB, com cinco cópias; demais ações seguem essa rotação.
- Backup completo é manual. Consulte [Banco e backup](SEGURANCA_BANCO.md).
