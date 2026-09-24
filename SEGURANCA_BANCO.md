# Proteger o banco de manifestações

## Migrar o histórico existente

Feche a interface e o DB Browser e suspenda qualquer consulta em andamento. Instale esta versão e confirme `nfe-consulta --version` (0.9.4). No PowerShell:

```powershell
nfe-consulta --criptografar-banco "$HOME\Downloads\nfe_manifestacoes_seguro.db" --banco "$HOME\Downloads\nfe_manifestacoes.db"
```

Digite uma senha longa e única duas vezes (mínimo de 12 caracteres). **Guarde a senha pelo procedimento da empresa**: sem ela, os dados do banco protegido não poderão ser recuperados. A senha não aparece nos argumentos do comando nem no ZIP. O programa cria outro banco, verifica sua integridade e as contagens das tabelas, preserva o original e não consulta a SEFAZ.

Confira, usando o caminho **seguro**:

```powershell
nfe-consulta --status --cnpj 16840128000101 --banco "$HOME\Downloads\nfe_manifestacoes_seguro.db"
```

Compare o `ultNSU` ao do banco original antes de voltar a sincronizar. Para as consultas seguintes, passe sempre `--banco "$HOME\Downloads\nfe_manifestacoes_seguro.db"`. O aplicativo não atualiza os dois bancos em conjunto. Ao iniciar, a interface gráfica dá preferência ao banco protegido em `dados/`, se existir, e depois ao de Downloads; confirme visualmente o caminho selecionado.

## Abrir no DB Browser

Use uma instalação do **DB Browser for SQLite que inclua SQLCipher**, selecione `nfe_manifestacoes_seguro.db` e informe a senha no diálogo; use os padrões SQLCipher 4. A aba **Navegar dados** mostra `manifestacoes` e `estado_distribuicao`. Abra em modo somente leitura para evitar edições acidentais. O DB Browser SQLite sem SQLCipher e o `sqlite3` padrão do Python não conseguem abrir o banco protegido.

## Escopo da proteção

SQLCipher protege o conteúdo do arquivo `.db` quando ele está fechado. **O banco original continua legível** depois da migração; siga a política de retenção e descarte da TI quando terminar a conferência. Arquivos `CHAVES.txt`, planilhas XLSX/CSV e cópias de backup também continuam sem criptografia, a menos que sejam protegidos separadamente. A proteção do banco não substitui permissões de acesso no Windows nem o controle de acesso à conta que conhece a senha.

Não salve a senha em script, histórico do PowerShell, argumento `--senha` ou nome de arquivo. Se esquecer a senha, o original ou um backup preservado será necessário para nova migração. Antes de mover o banco protegido para outro computador, leve também a senha pelo procedimento aprovado pela TI.

## Atalho de atualização

Com `entrada/CHAVES.txt` e `dados/nfe_manifestacoes_seguro.db` na pasta do projeto, basta executar `nfe-consulta --atualizar`; a planilha vai para `saidas/`. Se ambos os arquivos permanecerem em Downloads, o atalho usa Downloads e salva lá. O programa pede a senha a cada execução e mostra os caminhos utilizados. O atalho nunca troca automaticamente para o banco antigo.

Para gerar somente a planilha com o histórico salvo, sem acessar a SEFAZ, use `nfe-consulta --excel`. O comando pede a senha do banco protegido.

Ao mover o banco protegido, feche o aplicativo e o DB Browser, faça um backup conforme a política da empresa e confira o `ultNSU` no novo caminho. Mantenha uma única cópia ativa para as próximas sincronizações.
