# Dossiê técnico e de segurança — versão 1.0

## Arquitetura

A v1 mantém Python e separa a aplicação em camadas.

- `servico.py`: orquestra consulta local, sincronização e exportação.
- `gui.py`: interface Tkinter. Chama a camada de serviço diretamente.
- `cli.py`: interface de terminal.
- `distribuicao.py`: comunicação com NFeDistribuicaoDFe.
- `banco.py`: SQLite/SQLCipher, eventos, cursor NSU e pausa preventiva.
- `xlsx_writer.py`: exportação Excel.

A GUI não executa a CLI em subprocesso. GUI e CLI usam o mesmo fluxo de aplicação.

## Rede e certificado

A atualização remota usa:

`https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx`

O certificado é lido do repositório do usuário do Windows. A chave privada não é exportada pelo aplicativo.

A operação local e a geração de Excel não exigem acesso à SEFAZ.

## Controles relevantes

- XML processado com `defusedxml`.
- Limites de tamanho para TXT, SOAP e documentos distribuídos.
- SQL parametrizado.
- Cursor NSU e eventos gravados em transação.
- Rejeição 656 registra pausa preventiva no banco.
- Sincronização completa recente evita repetição imediata.
- Planilha gravada de forma atômica.
- Conteúdo externo exportado como texto para reduzir risco de fórmula.
- Consulta local não cria banco ausente por acidente.
- Banco SQLCipher opcional com migração explícita e preservação do original.
- Sem servidor web, porta de escuta ou telemetria.

## CLI v1

```powershell
nfe-consulta atualizar
nfe-consulta excel
nfe-consulta status
nfe-consulta gui
```

A sintaxe longa da 0.9.4 permanece somente para compatibilidade interna durante a transição.

## Dados armazenados

O banco pode conter:

- CNPJ consultado;
- chave da NF-e;
- código e descrição do evento;
- data do evento;
- protocolo;
- NSU;
- estado da distribuição;
- registro de pausa preventiva.

TXT e XLSX não são criptografados automaticamente.

## Limitações

- O histórico recuperável depende da janela disponibilizada pelo Ambiente Nacional.
- “Sem evento localizado” não comprova ausência histórica de manifestação.
- Limites de consumo podem ser compartilhados com outros sistemas do mesmo CNPJ.
- A aplicação não substitui revisão de TI, política de backup ou controle de acesso ao certificado.
- A interface precisa ser validada em desktop Windows corporativo.
- Os testes automatizados não substituem teste integrado com certificado real.

## Verificação sugerida

1. Revisar o diff entre v0.9.4 e v1.0.
2. Validar dependências e origem dos pacotes.
3. Rodar `py -m pytest -q`.
4. Testar `nfe-consulta excel` com banco de teste.
5. Testar `nfe-consulta atualizar` em ambiente controlado.
6. Confirmar tratamento de 137, 138 e 656.
7. Confirmar permissões e backup do banco.
