# Consulta de manifestação YAB — versão 0.9.4

O código-fonte, os testes, o instalador e os manuais estão juntos. **Não há certificado digital, senha, chaves reais, banco de dados ou resultado fiscal dentro deste pacote.**

1. TI: leia [REVISAO.md](REVISAO.md) e [MANUAL_DE_INSTALACAO.md](MANUAL_DE_INSTALACAO.md).
2. Instale pelo `INSTALAR.cmd` ou pelo comando de instalação descrito no manual.
3. Dê duplo clique em `ABRIR_CONSULTA.cmd` ou use `nfe-consulta --gui` para abrir a interface gráfica. O botão verde gera Excel com o banco local; a atualização da SEFAZ tem um botão separado. `ABRIR_CONSULTA_TEXTO.cmd` mantém o assistente em texto.
4. A planilha padrão é `saidas/Consulta_Manifestacao_YAB.xlsx`; a aba tem o mesmo nome sem `.xlsx`.

Na primeira utilização, coloque seu `CHAVES.txt` em `entrada` ou selecione outro caminho no assistente. Quem já tem `nfe_manifestacoes.db` em Downloads pode reutilizá-lo; o assistente detecta esse arquivo, sem copiá-lo.

Para todos os comandos: `py -m nfe_consulta.cli --help` ou `py -m nfe_consulta.cli -help`.

Para proteger o histórico existente, veja [SEGURANCA_BANCO.md](SEGURANCA_BANCO.md).

Atalho para atualizar com banco seguro em `dados/` e TXT em `entrada/`, ou com ambos em Downloads: `nfe-consulta --atualizar`.

Atalho para gerar somente a planilha do banco seguro, sem SEFAZ: `nfe-consulta --excel`.
