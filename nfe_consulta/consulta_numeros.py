"""Consulta em lote de números de NF-e exclusivamente no banco local."""
from contextlib import closing
from pathlib import Path
import re

from nfe_consulta.banco import consultar_chave_local
from nfe_consulta.export_control import cancellable_rows
from nfe_consulta.seguranca_banco import abrir_banco
from nfe_consulta.servico import ResultadoExecucao
from nfe_consulta.xlsx_writer import gravar_xlsx


def ler_numeros(caminho: Path, *, max_numeros=10_000):
    if caminho.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('TXT de notas excede 2 MiB.')
    numeros = {}
    try:
        lines = caminho.read_text(encoding='utf-8-sig').splitlines()
    except UnicodeError as exc:
        raise ValueError('Salve o TXT de notas com codificação UTF-8.') from exc
    count = 0
    for index, line in enumerate(cancellable_rows(lines), 1):
        value = line.strip()
        if not value:
            continue
        count += 1
        if count > max_numeros:
            raise ValueError(f'TXT excede {max_numeros:,} números de notas.')
        if not re.fullmatch(r'[0-9]{1,9}', value) or int(value) == 0:
            raise ValueError(f'Linha {index}: informe somente um número de nota entre 1 e 999999999, sem cabeçalho ou pontuação.')
        numeros.setdefault(int(value), [])
    if not numeros:
        raise ValueError('Nenhum número foi encontrado no TXT enviado.')
    return numeros


def executar_consulta_numeros(arquivo: Path, banco: Path, saida: Path, cnpj: str, *, senha=None, max_numeros=10_000):
    numbers = ler_numeros(arquivo, max_numeros=max_numeros)
    with closing(abrir_banco(banco, senha, somente_leitura=True)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'manifestacoes' not in tables:
            raise ValueError('Banco de manifestações inválido.')
        sources = [table for table in ('manifestacoes','informacoes_nfe','xml_documentos') if table in tables]
        # Uma leitura das chaves locais evita uma consulta completa por número.
        sql = ' UNION '.join(f'SELECT chave FROM {table} WHERE cnpj=?' for table in sources)
        found = 0
        for (key,) in cancellable_rows(connection.execute(sql, [cnpj]*len(sources))):
            if not re.fullmatch(r'[0-9]{44}', key):
                continue
            number = int(key[25:34])
            if number in numbers:
                found += 1
                if found > 100_000:
                    raise ValueError('Mais de 100.000 notas correspondem ao TXT. Reduza a lista de números.')
                numbers[number].append(key)
        results = []
        for keys in cancellable_rows(numbers.values()):
            for key in cancellable_rows(sorted(keys)):
                results.append(consultar_chave_local(connection, key, cnpj))
    coverage = 'Histórico local; consulta por números; todas as correspondências incluídas; sem chamada à SEFAZ.'
    gravar_xlsx(str(saida), results, coverage,
                numeros_solicitados={number:len(keys) for number,keys in numbers.items()})
    return ResultadoExecucao(tuple(results), coverage, saida)
