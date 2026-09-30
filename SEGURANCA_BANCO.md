# Banco de manifestações — segurança e continuidade

O aplicativo usa o banco selecionado na aba **Atualizar**. Para SQLCipher,
grave a senha em `secrets/db-password.txt` da mesma instalação. O banco e a
senha não entram no pacote de release.

## Atualizar sem perder o histórico

Antes de substituir o código, pare o servidor Web e faça backup do banco e da
pasta `secrets` em local protegido. Preserve o caminho configurado em
`secrets/db-path.txt`. Depois de reiniciar, confira o `ultNSU`, `maxNSU` e a
data de última gravação na tela **Status**.

Não alterne entre cópias do banco nem avance manualmente o `ultNSU`: isso pode
separar o histórico ou deixar documentos sem processamento. Um `maxNSU` de
outra cópia não é um cursor para recuperar uma rejeição 656.

## Abrir no DB Browser

Para um banco protegido, use uma edição do DB Browser com suporte a SQLCipher
4, preferencialmente em modo somente leitura. Feche o aplicativo antes de
restaurar backups. Registre a data, o cursor e a origem do backup antes de
adotá-lo como banco ativo.

SQLCipher protege o arquivo do banco, mas não criptografa automaticamente TXT,
planilhas exportadas, logs e backups. Restrinja o acesso a esses arquivos e à
pasta `secrets` conforme a política da empresa.


Inclua também `dados/admin_accounts.db` no backup: ele guarda contas e sessões administrativas. Esse arquivo usa SQLite; SQLCipher protege apenas o banco fiscal configurado. Pare o processo antes de copiar ou restaurar os bancos.
