# Manual de uso — Consulta de Manifestação NF-e

## Consulta

A tela **Consulta** trabalha exclusivamente com o histórico salvo no banco central. Ela não acessa a SEFAZ.

Filtros disponíveis:

- data inicial e final do evento;
- número da NF;
- série;
- chave de acesso;
- tipo de manifestação.

Os resultados são exibidos em páginas de até 100 registros.

## Exportar Excel

Após executar uma consulta, use **Exportar Excel**.

A planilha contém exatamente os registros correspondentes aos filtros aplicados na tela, com:

- número da NF;
- série;
- chave;
- código e descrição da manifestação;
- data do evento;
- protocolo;
- NSU;
- data de recebimento no banco.

## Consulta por arquivo

Para trabalhar com uma lista específica de NF-e, use a seção **Consulta por arquivo** e selecione um `CHAVES.txt` com uma chave de 44 dígitos por linha.

Esse fluxo também utiliza somente o banco central.

## Status

A tela **Status** apresenta:

- data da última gravação;
- `ultNSU`;
- `maxNSU`;
- estado da sincronização;
- próxima sincronização permitida.

## Atualizar

A área **Atualizar** exige login administrativo.

Ela permite:

- configurar o banco central;
- configurar o certificado A1;
- sincronizar o banco com o serviço `NFeDistribuicaoDFe`.

Após uma tentativa válida, o sistema aplica o cooldown configurado. A rejeição 656 possui tratamento próprio.

## Sincronização automática

Em produção, a aplicação sincroniza automaticamente com a SEFAZ às **08:00 de segunda a sexta-feira**, desde que o serviço Web esteja em execução.

A rotina utiliza o mesmo banco, certificado e cooldown da área **Atualizar**. Se uma sincronização manual estiver em andamento ou o cooldown ainda estiver ativo, a execução automática é ignorada.

O resultado é registrado no log de auditoria com a ação `sefaz_sync_auto`.

## Observações

- ausência de evento no banco não comprova que a NF-e nunca recebeu manifestação;
- a consulta Web nunca chama a SEFAZ;
- banco, certificado e senhas permanecem no servidor;
- a interface pública da aplicação é exclusivamente Web.
