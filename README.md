# AtlasDFE

Aplicação Web para consulta local de manifestações de NF-e, importação de dados de XML e geração de relatórios Excel/CSV. A sincronização usa o serviço `NFeDistribuicaoDFe` do Ambiente Nacional.

## Operação

| Item | Configuração |
| --- | --- |
| Runtime | Python 3.11+; CI com Python 3.12 |
| Servidor | FastAPI/Uvicorn; um processo, um worker |
| Banco fiscal | SQLite ou SQLCipher; caminho selecionado em Admin |
| Acesso | Login por e-mail ou usuário; cadastro próprio com perfil comum |
| Sincronização SEFAZ | Windows com PowerShell e certificado A1 |
| Janela AtlasDFE | **22:00 inclusive até 04:00 exclusiva, Brasília (UTC−3)** |
| Disparos automáticos | **22:00, 23:00, 00:00, 01:00, 02:00 e 03:00** por padrão; configuráveis no Admin |
| Janela solicitada ao Qive | **08:00–18:00**, incluindo novas tentativas |
| Recuperação `consNSU` | Pausada por padrão: `NFE_RECOVERY_ENABLED=0` |
| Alertas de e-mail | Somente Operação não Realizada (`210240`) |
| Retenção | Downloads: 24 horas; histórico de sincronização: 30 dias |

Em **Admin → Disparos automáticos**, ative/desative a agenda e escolha horários e dias sem reiniciar. São aceitos até seis horários dentro da janela, separados por pelo menos 60 minutos. A configuração salva prevalece sobre a ativação inicial do lançador.

A interface e os testes locais também executam em Linux. O transporte SEFAZ e a leitura de certificados usam PowerShell; a implantação documentada para sincronização é Windows. A aprovação da CI Linux não valida comunicação real com a SEFAZ.

## Instalação Windows

Extraia o ZIP de [Releases](https://github.com/MagroNego/ConsultaManifestacao_DFE/releases) em pasta definitiva. Execute no PowerShell dessa pasta:

```powershell
.\INSTALAR.cmd
.\CONFIGURAR_ADMIN.cmd
.\INICIAR_WEB.cmd
```

Acesse `http://127.0.0.1:8080`. Entre com a conta administrativa e configure o banco de manifestações existente e o certificado A1. As credenciais, o certificado e o banco fiscal não acompanham o pacote. Procedimento completo: [Instalação](MANUAL_DE_INSTALACAO.md).

## Recursos

- Consulta de manifestações por período do evento, nota, chave, tipo e situação.
- Emissão: notas importadas, itens, impostos, retenções e cancelamentos registrados.
- Consulta por TXT de chaves ou números de notas, exportação de todas as páginas filtradas e Downloads.
- Vínculos de CT-e recebidos por eventos, com os campos efetivamente disponíveis.
- Sincronização automática e manual administrativa, cursor NSU e diagnóstico de falhas.
- Contas comuns, administração de usuários, remetente SMTP e e-mail de teste.

Consultas, importações e relatórios trabalham no banco local. O AtlasDFE não transmite manifestações ou cancelamentos. Novos XMLs são processados e os dados necessários ficam no banco; o original deve ser obtido no Synchro. Respostas SEFAZ pendentes de processamento são preservadas temporariamente.

## Distribuição e Qive

O suporte confirmou o uso de `distNSU` pelo Qive e aceitou solicitar a configuração das 08:00 às 18:00. O AtlasDFE aplica sua própria janela no backend, inclusive às consultas manuais, recuperações e retentativas. Uma requisição já enviada pode terminar após 04:00; não se inicia outra fora da janela.

Os detalhes do atendimento, o comportamento do cursor, os resultados das duas noites de teste e a alternativa comercial Gateway estão em [Distribuição DF-e e Qive](DISTRIBUICAO_DFE_QIVE.md). Horários separados não são documentados como garantia de ausência de rejeição 656.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [Leia primeiro](LEIA_PRIMEIRO.md) | Sequência inicial |
| [Instalação](MANUAL_DE_INSTALACAO.md) | Requisitos, instalação, configuração e atualização |
| [Uso](MANUAL_DE_USO.md) | Telas, relatórios, contas e diagnóstico |
| [Distribuição DF-e e Qive](DISTRIBUICAO_DFE_QIVE.md) | Janelas, NSU, 656, consNSU e informações do suporte |
| [Servidor Web](SERVIDOR_WEB.md) | Processo, rede, variáveis e SMTP |
| [Banco e backup](SEGURANCA_BANCO.md) | Arquivos persistentes, backup e restauração |
| [Arquitetura](ARQUITETURA.md) | Componentes, transações e limites |
| [Histórico](CHANGELOG.md) | Alterações por versão |

## Desenvolvimento e pacote

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m compileall -q nfe_consulta
python scripts/package_release.py
```

A CI testa Windows e Linux com dados sintéticos, sem chamadas reais à SEFAZ nem envio real de e-mail. O pacote contém código, recursos, lançadores e documentação; não contém dados operacionais.

A versão declarada permanece `2.6.0`. A branch `main` pode conter correções posteriores ao ZIP dessa release. O workflow não substitui uma release existente: um pacote novo exige atualização de versão e nova publicação.
