# Manual de uso — v1.0

## Abrir

Use `ABRIR_CONSULTA.cmd` ou:

```powershell
nfe-consulta gui
```

## Arquivos

A tela usa três caminhos:

- **CHAVES.TXT**: uma chave de NF-e por linha.
- **BANCO**: histórico local de eventos e cursor NSU.
- **PLANILHA**: arquivo `.xlsx` gerado.

Os botões `…` alteram os caminhos.

## Atualizar SEFAZ

Clique em **Atualizar SEFAZ**.

O aplicativo:

1. abre o banco;
2. seleciona o certificado compatível com o CNPJ;
3. continua do último NSU salvo;
4. grava os novos eventos;
5. cruza o histórico com as chaves do TXT;
6. gera a planilha.

O campo **Lotes** limita quantos lotes de distribuição podem ser processados na execução.

Se houver rejeição 656, a pausa é gravada no banco. Não tente contornar a pausa repetindo chamadas por fora do aplicativo.

## Gerar Excel

Clique em **Gerar Excel** para trabalhar somente com os dados já existentes no banco. Nenhuma chamada à SEFAZ é feita.

## Resultados

A tabela mostra número, série, manifestação, data e chave de acesso.

Use a busca para localizar uma nota ou chave. Ao selecionar uma linha, o histórico aparece na faixa inferior.

**Abrir Excel** abre a última planilha gerada.

## CLI

Uso normal:

```powershell
nfe-consulta atualizar
nfe-consulta excel
nfe-consulta status
nfe-consulta gui
```

Com caminhos explícitos:

```powershell
nfe-consulta atualizar C:\caminho\CHAVES.txt `
  --banco C:\caminho\historico.db `
  --saida C:\caminho\resultado.xlsx
```

## Banco criptografado

```powershell
nfe-consulta proteger-banco origem.db destino_seguro.db
```

A migração cria um novo arquivo e preserva o original.

## Observações

- O aplicativo consulta manifestação por distribuição de DF-e e mantém um histórico local.
- A primeira sincronização pode exigir vários lotes.
- Eventos antigos podem não estar mais disponíveis no Ambiente Nacional.
- O banco deve ser mantido entre as execuções para preservar o cursor NSU e o histórico.
