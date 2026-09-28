# Consulta de Manifestação NF-e — v2.2.0-dev

Esta versão usa uma interface Web para consultar manifestações, exportar Excel,
ver o estado do banco e sincronizar com a SEFAZ. A consulta e as exportações
usam somente o banco local; a sincronização exige login administrativo.

## Primeira instalação no Windows

1. Extraia o pacote em uma pasta definitiva.
2. Execute `INSTALAR.cmd` e depois `CONFIGURAR_ADMIN.cmd`.
3. Execute `INICIAR_WEB.cmd` e abra `http://127.0.0.1:8080` no navegador.
4. Configure o banco existente e o certificado na aba **Atualizar**.

Leia `MANUAL_DE_INSTALACAO.md` antes de instalar no servidor e
`MANUAL_DE_USO.md` para usar a interface.

## Atualização de uma instalação existente

Feche o aplicativo, faça backup da pasta atual e instale o novo código na
mesma pasta. Preserve `dados`, `secrets`, logs e os caminhos já configurados.
Reinicie o aplicativo e confirme `v2.2.0-dev` no cabeçalho. Não altere manualmente
o `ultNSU` do banco.

O pacote não inclui banco real, senha ou certificado. A instalação em rede
interna e o agendamento estão descritos em `SERVIDOR_WEB.md`.
