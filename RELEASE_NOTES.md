# Consulta de Manifestação NF-e v2.3.0

- Nova aba XMLs com o leitor de saída integrado: importe ZIPs mensais ou XMLs completos.
- Arquivo cumulativo no banco fiscal, deduplicado pela chave, com XML original preservado.
- Relatórios de notas, itens/impostos e PIS/COFINS retidos, busca, período da emissão e exportação Excel/CSV.
- Baixar XML e Ver itens disponíveis na consulta de manifestações para arquivos importados.
- Importação e registros de lote restritos ao administrador; operações locais, sem chamadas à SEFAZ.
- Os XMLs seguem a criptografia SQLCipher do banco, quando habilitada.
- Agendamento às 08:00 e 15:00 de Brasília, proteção do botão e cooldown de 60 minutos preservados.

## Atualização

Pare o app, faça backup do banco fiscal, substitua código e lançadores e execute INSTALAR.cmd. Preserve dados, secrets, banco, logs e certificado; reinicie com INICIAR_WEB.cmd.

Depois, entre como administrador e use XMLs → Importar lote mensal. As tabelas novas são criadas na primeira importação. Importe apenas XMLs completos de NF-e emitidas pelo CNPJ do aplicativo; eventos e resumos não contêm os itens da nota.

O pacote é publicado após os testes de Linux e Windows passarem.
