# Consulta de Manifestação NF-e v2.2.0

Versão estável com consulta local de manifestações, exportação Excel, administração de acessos e sincronização com o Ambiente Nacional da NF-e.

## Alterações

- Sincronização automática a cada 8 horas: 00:00, 08:00 e 16:00, horário de Brasília, todos os dias.
- Registro de conclusão por janela, recuperação após reinício e respeito ao cooldown da SEFAZ.
- Contas individuais, sessões revogáveis e histórico administrativo.
- Alertas SMTP para novos eventos 210240, com fila persistente.
- Emitente na consulta e exportação; últimas sincronizações no Status.
- Remoção da visualização de cancelamentos e do lançador específico de teste.
- Documentação de instalação, atualização, uso, implantação e arquitetura revisada.

## Instalação e atualização

Baixe `ConsultaManifestacao_DFE-v2.2.0.zip`. No Windows, execute `INSTALAR.cmd`, `CONFIGURAR_ADMIN.cmd` na primeira instalação e `INICIAR_WEB.cmd`.

Para atualizar, pare o aplicativo, faça backup, substitua o código e os lançadores e execute o instalador para atualizar dependências. Preserve banco, `dados`, `secrets`, logs e certificado. Remova `NFE_AUTO_SYNC_ONCE_DATE` do ambiente caso tenha sido configurada. O lançador Windows habilita a rotina recorrente; `NFE_AUTO_SYNC_ENABLED=0` a desativa.

O pacote não contém banco fiscal, credenciais, certificado ou arquivos operacionais. Consulte `MANUAL_DE_INSTALACAO.md` no pacote. A release inclui checksum SHA-256 e só é publicada após aprovação dos testes automatizados em Windows e Linux.
