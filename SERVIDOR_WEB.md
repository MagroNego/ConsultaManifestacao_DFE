# Implantação Web — v2.4.0

## Processo e rede

Execute **um único processo com um worker** e mantenha o banco preferencialmente no disco local. O comando `nfe-consulta-web` e o lançador Windows iniciam com um worker.

A aplicação escuta em `127.0.0.1:8080`. Publique o acesso interno por HTTPS em IIS ou outro reverse proxy. Configure o serviço para iniciar com o sistema operacional e reiniciar após falhas. A conta do serviço precisa acessar o banco, o certificado e as pastas `dados`, `secrets` e `logs`.

```text
NFE_WEB_ENV=production
NFE_WEB_HOST=127.0.0.1
NFE_WEB_PORT=8080
NFE_WEB_FORWARDED_ALLOW_IPS=127.0.0.1
```

Se o proxy estiver em outra máquina, informe somente os endereços confiáveis em `NFE_WEB_FORWARDED_ALLOW_IPS`. O endpoint `GET /healthz` retorna somente estado básico e versão, sem indicar a disponibilidade do banco.

## Controle de acesso

Consultas e exportações não exigem login. **Admin**, a importação XML e os registros de lote exigem uma sessão administrativa válida. A validação é feita no servidor antes de processar uploads. Contas sem perfil Admin não entram nessa área.

Configure ou redefina a conta com `CONFIGURAR_ADMIN.cmd` (Windows) ou `python -m nfe_consulta.web.configure_admin` (Linux). A senha fica como hash no banco de contas e os tokens são mantidos no servidor. Sessões expiram por inatividade (30 minutos por padrão) e são revogadas no logout ou redefinição da senha. Cookies são HttpOnly e SameSite=Strict; Secure é aplicado quando a requisição usa HTTPS. O modo HTTP local continua funcional; prefira HTTPS na implantação definitiva. Configure o proxy e `NFE_WEB_FORWARDED_ALLOW_IPS` apenas com origens confiáveis.

## Segredos do servidor

`INICIAR_WEB.cmd` cria `secrets/web-csrf-secret.txt` na primeira execução e preserva o arquivo nos reinícios. Em outro método de inicialização, configure esse arquivo com pelo menos 32 caracteres aleatórios ou defina `NFE_WEB_CSRF_SECRET` no ambiente do serviço.

As senhas do banco, certificado e SMTP são lidas dos arquivos de `secrets`; `NFE_DATABASE_PASSWORD`, `NFE_CERT_PASSWORD` e `NFE_ADMIN_PASSWORD` não são fontes de senha.

Restrinja as permissões NTFS ou Unix das pastas operacionais à conta do processo e aos administradores autorizados.

## Banco fiscal

Em **Admin**, selecione o banco existente. A configuração é salva em `secrets/db-path.txt`; a senha SQLCipher fica em `secrets/db-password.txt`. A tela administrativa identifica se o arquivo usa SQLite ou SQLCipher.

SQLCipher é opcional e protege o banco fiscal em repouso. Não criptografa automaticamente exportações, logs, o banco de contas ou arquivos de segredo. Consulte [SEGURANCA_BANCO.md](SEGURANCA_BANCO.md) para continuidade e restauração.

## Certificado A1

### Arquivo PFX/P12

Armazene o certificado em pasta protegida, por exemplo `C:\Certificados\certificado.pfx`, e configure-o em **Admin**. A conta do serviço precisa ler o arquivo. O aplicativo guarda o caminho em `secrets/cert-path.txt` e a senha em `secrets/cert-password.txt`; não copia o certificado para o projeto.

### Windows Certificate Store

O repositório pode ser `CurrentUser` ou `LocalMachine`. Para uma conta de serviço, instale o A1 em `Cert:\LocalMachine\My` e conceda acesso à chave privada para essa conta.

```text
NFE_CERT_STORE=LocalMachine
NFE_CERT_THUMBPRINT=<impressão digital do certificado selecionado>
```

No Linux, use certificado por arquivo. O certificado e o banco usados pela rotina automática são os mesmos configurados na administração.

## Sincronização nos horários fixos de 08:00 e 15:00

```text
NFE_AUTO_SYNC_ENABLED=1
NFE_AUTO_SYNC_WEEKDAYS=0,1,2,3,4,5,6
NFE_AUTO_SYNC_MAX_LOTES=50
```

As janelas são **08:00 e 15:00, horário de Brasília, todos os dias**, independentemente do fuso do sistema operacional. Segunda-feira corresponde a `0` e domingo a `6`.

O lançador Windows ativa a rotina se `NFE_AUTO_SYNC_ENABLED` não estiver definida. Defina `0` para desativar. No Linux ou em um serviço configurado diretamente, defina as variáveis no ambiente do processo. `WEB_CONFIG.example` é apenas referência e não é carregado automaticamente.

O aplicativo precisa permanecer ativo. A conclusão fica em `controle_agendamento_intervalo`. Ao reiniciar, uma janela já concluída não se repete. Se houver atraso, apenas a janela mais recente é recuperada. Falhas e resultados parciais são retomados na próxima janela, respeitando cooldown e trava. Antes das 08:00, aguarda a primeira janela do dia. Não execute outra instância contra o mesmo banco.

As variáveis antigas `NFE_AUTO_SYNC_ONCE_DATE`, `NFE_AUTO_SYNC_INTERVAL_HOURS`, `NFE_AUTO_SYNC_HOUR`, `NFE_AUTO_SYNC_MINUTE` e `NFE_SEFAZ_COOLDOWN_MINUTES` são ignoradas; remova-as da configuração. A rotina definitiva usa 08:00 e 15:00 e cooldown de 60 minutos.

## Cooldown e rejeição 656

O bloqueio padrão é de **60 minutos**, persistido no banco e validado no backend. Reiniciar o aplicativo não o remove. A rejeição 656 preserva o cursor local, registra a pausa e permite consultar o NSU enviado e o informado no retorno, quando disponível.

Não avance o cursor com base na rejeição e não alterne entre cópias de banco para tentar contornar o bloqueio. Outros sistemas de distribuição do mesmo CNPJ também podem afetar a sequência e o consumo do serviço.

## Alertas SMTP

Configure no ambiente do processo:

```text
NFE_SMTP_HOST=<servidor SMTP>
NFE_SMTP_PORT=587
NFE_SMTP_SECURITY=starttls
NFE_SMTP_FROM=<remetente autorizado>
NFE_SMTP_USER=<usuário, quando necessário>
```

Use `ssl` e a porta correspondente quando o servidor exigir TLS direto. Grave a senha em `secrets/smtp-password.txt`. Reinicie após alterar variáveis. Cadastre os destinatários pela interface; não edite manualmente `secrets/email-recipients.json`.

Sem host e remetente configurados, não há envio. A fila `notificacoes_email` persiste no banco fiscal. Falhas temporárias permanecem pendentes; destinatários removidos e rejeições permanentes encerram os avisos correspondentes. A sincronização não é repetida para reenviar e-mails. Uma interrupção após a aceitação SMTP pode causar duplicidade.

## Auditoria e backup

O log fica em `logs/web_audit.log`, com rotação. Registra responsável, ação, resultado e dados operacionais; não registra senhas ou chaves de NF-e. `NFE_WEB_AUDIT_LOG` permite mudar o caminho.

Faça backup do banco fiscal, `dados/admin_accounts.db`, `secrets`, certificado e logs em local protegido. Pare o processo antes de copiar os bancos para um backup consistente ou restaurá-los. Após restauração, confira versão, acesso administrativo, caminho do banco e cursores em **Status** antes de retomar a operação.
