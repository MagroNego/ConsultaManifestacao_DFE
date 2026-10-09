"""Recuperação pontual de lacunas, sem alterar o cursor distNSU."""
from dataclasses import replace
from nfe_consulta.distribuicao import consultar_nsu, preservar_resposta, _erro_consumo_indevido
from nfe_consulta.parser_distribuicao import parse_retorno_distribuicao
from nfe_consulta.modelos import NfeErroResposta


def recuperar_intervalos(banco, cnpj, uf, certificado, destinatarios=(), limite=10):
    if not 1 <= limite <= 10:
        raise ValueError('Limite de recuperação deve estar entre 1 e 10')
    if banco.pausa_ativa(cnpj):
        return 0
    inseridos = 0
    # Uma reserva sem resposta pode sobreviver à interrupção do processo.
    with banco.conexao:
        banco.conexao.execute("UPDATE consultas_nsu SET resultado='repetir' WHERE cnpj=? AND resultado='pendente' AND resposta_xml IS NULL AND tentado_em<datetime('now','-1 hour')", (cnpj,))

    def processar(identificador, nsu, retorno):
        nonlocal inseridos
        if retorno.status_codigo == 656:
            exc = _erro_consumo_indevido(retorno)
            banco.pausar_distribuicao(cnpj, str(exc))
            with banco.conexao:
                banco.conexao.execute("UPDATE consultas_nsu SET resultado='repetir' WHERE id=?", (identificador,))
            raise exc
        if retorno.status_codigo == 137:
            if retorno.documentos:
                raise NfeErroResposta('Resposta 137 com documentos; intervalo permanece pendente')
            with banco.conexao:
                banco.conexao.execute("UPDATE consultas_nsu SET resultado='indisponivel' WHERE id=?", (identificador,))
            return
        if retorno.status_codigo != 138 or len(retorno.documentos) != 1 or retorno.documentos[0][0] != nsu:
            raise NfeErroResposta('Resposta consNSU inesperada; intervalo permanece pendente')
        atual, maximo = banco.obter_estado(cnpj)
        inseridos += banco.salvar_retorno(cnpj, replace(retorno, ult_nsu=atual, max_nsu=maximo),
                                         destinatarios, atualizar_estado=False, consulta_nsu_id=identificador)

    for identificador, nsu, xml in banco.conexao.execute(
        "SELECT id,nsu,resposta_xml FROM consultas_nsu WHERE cnpj=? AND resultado='pendente' AND resposta_xml IS NOT NULL ORDER BY id",
        (cnpj,)).fetchall():
        processar(identificador, nsu, parse_retorno_distribuicao(xml))

    for _ in range(limite):
        banco.conexao.execute('BEGIN IMMEDIATE')
        try:
            usadas = banco.conexao.execute(
                "SELECT COUNT(*) FROM consultas_nsu WHERE cnpj=? AND tentado_em>=datetime('now','-1 hour')", (cnpj,)).fetchone()[0]
            if usadas + banco.consultas_na_ultima_hora(cnpj) >= 20:
                banco.conexao.rollback()
                break
            nsu = banco.proximo_nsu_faltante(cnpj)
            if nsu is None:
                banco.conexao.rollback()
                break
            identificador = banco.conexao.execute(
                'INSERT INTO consultas_nsu(cnpj,nsu) VALUES (?,?)', (cnpj,nsu)).lastrowid
            banco.conexao.commit()
        except Exception:
            banco.conexao.rollback()
            raise

        def guardar(xml):
            with banco.conexao:
                banco.conexao.execute('UPDATE consultas_nsu SET resposta_xml=? WHERE id=?', (xml,identificador))
        try:
            with preservar_resposta(guardar):
                retorno = consultar_nsu(cnpj, uf, nsu, certificado)
        except Exception:
            with banco.conexao:
                banco.conexao.execute("UPDATE consultas_nsu SET resultado='repetir' WHERE id=? AND resposta_xml IS NULL", (identificador,))
            raise
        processar(identificador, nsu, retorno)
    return inseridos
