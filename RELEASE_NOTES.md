# Consulta de Manifestação NF-e v2.4.0

- Login obrigatório para consultas, Status, leitor XML, exportações e downloads, inclusive por URL direta.
- Perfis Consulta (visualização), Fiscal (visualização, XML e exportações) e Administrador (acesso completo).
- Gerenciamento de contas/perfis em Atualizar → Gerenciar acessos, com Consulta como padrão para novas contas.
- Alterações de senha, perfil e estado da conta encerram suas sessões; último administrador ativo protegido.
- Administradores e senhas existentes preservados na migração, sem recriar contas a partir de secrets. Sessões antigas são revogadas na primeira atualização.
- Auditoria identifica usuários e perfis sem conteúdo fiscal dos XMLs ou senhas.

## Atualização

Pare o servidor. Faça backup do banco fiscal, dados/admin_accounts.db e secrets em local protegido. Substitua apenas código/lançadores, execute INSTALAR.cmd e reinicie com INICIAR_WEB.cmd. Preserve dados, secrets, banco, logs e certificado.

Faça login novamente com o administrador existente. Cadastre as contas pessoais em Atualizar → Gerenciar acessos e escolha os perfis. Não substitua nem exclua o banco de contas existente.

As permissões no app não configuram HTTPS, firewall ou proteção dos backups: mantenha o reverse proxy HTTPS e as permissões das pastas operacionais descritos em SERVIDOR_WEB.md.

O pacote é publicado após os testes de Linux e Windows passarem.
