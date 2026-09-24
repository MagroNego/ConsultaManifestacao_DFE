# Consulta de Manifestação YAB — versão 1.0

Este pacote contém código-fonte, testes, instalador e documentação. Não inclui certificado digital, senha, banco real, chaves reais ou resultado fiscal.

## Início rápido

1. Leia `MANUAL_DE_INSTALACAO.md`.
2. Execute `INSTALAR.cmd`.
3. Abra `ABRIR_CONSULTA.cmd`.
4. Coloque o TXT em `entrada/CHAVES.txt` ou escolha outro arquivo na tela.
5. Mantenha o mesmo banco entre as sincronizações.

CLI principal:

```powershell
nfe-consulta atualizar
nfe-consulta excel
nfe-consulta status
nfe-consulta gui
```

A planilha padrão é `saidas/Consulta_Manifestacao_YAB.xlsx`.

Para proteção do banco, consulte `SEGURANCA_BANCO.md`. Para revisão técnica e de segurança, consulte `REVISAO.md`.
