# Consulta de Manifestação NF-e — v2.2.0

## Primeira instalação

1. Extraia o pacote em uma pasta definitiva.
2. Execute `INSTALAR.cmd` e `CONFIGURAR_ADMIN.cmd`.
3. Execute `INICIAR_WEB.cmd` e abra http://127.0.0.1:8080.
4. Em **Atualizar**, configure o banco existente e o certificado A1.
5. Consulte o histórico em **Consulta** e acompanhe a sincronização em **Status**.

O lançador habilita a sincronização às **08:00 e 15:00 (Brasília)**. Mantenha o processo em execução. Para desativar, configure `NFE_AUTO_SYNC_ENABLED=0` antes de iniciar.

## Atualização

Pare a instalação, faça backup e substitua o código e os lançadores pela nova versão. Preserve `dados`, `secrets`, logs, certificado e os caminhos configurados. Execute `INSTALAR.cmd` para atualizar as dependências e reinicie por `INICIAR_WEB.cmd`. Confirme **2.2.0** no cabeçalho e confira o cursor NSU em **Status**.

O lançador de teste de data única foi retirado. Remova `NFE_AUTO_SYNC_ONCE_DATE` do ambiente, caso tenha sido configurada; a rotina final é recorrente nos horários fixos de 08:00 e 15:00.

Leia o [manual de instalação](MANUAL_DE_INSTALACAO.md) para o procedimento completo e o [manual de uso](MANUAL_DE_USO.md) para operar a aplicação.
