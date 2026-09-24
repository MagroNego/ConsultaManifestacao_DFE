# Proteger o banco de manifestações

## Criar banco protegido

Feche o aplicativo e o DB Browser. Depois execute:

```powershell
nfe-consulta proteger-banco dados\nfe_manifestacoes.db dados\nfe_manifestacoes_seguro.db
```

A senha deve ter pelo menos 12 caracteres. Ela é solicitada no terminal e não é colocada nos argumentos.

A migração:

1. verifica a integridade do banco original;
2. cria um novo banco SQLCipher;
3. exporta as tabelas;
4. verifica integridade e contagens;
5. preserva o arquivo original.

## Conferir

```powershell
nfe-consulta status --banco dados\nfe_manifestacoes_seguro.db
```

Compare o NSU com o banco original antes de adotar a cópia protegida como banco ativo.

## DB Browser

Para abrir o banco protegido, o DB Browser precisa ter suporte a SQLCipher. Use os padrões SQLCipher 4 e, de preferência, abra em modo somente leitura.

## Escopo

SQLCipher protege o arquivo de banco quando fechado. Não protege automaticamente:

- `CHAVES.txt`;
- planilhas XLSX;
- CSVs antigos;
- cópias do banco original;
- backups externos.

A proteção também não substitui ACLs do Windows nem o procedimento corporativo de gestão de senhas.

Mantenha uma única cópia ativa do banco para as sincronizações seguintes. Ter dois bancos sendo usados alternadamente separa o histórico e o cursor NSU.
