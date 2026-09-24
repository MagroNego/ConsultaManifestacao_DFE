from nfe_consulta.modelos import ResultadoConsulta


def formatar_resultado(resultado: ResultadoConsulta) -> str:
    linhas = [
        "Manifestacao NF-e \u2014 historico local",
        f"Chave: {resultado.chave}",
    ]

    linhas.append("")
    linhas.append("Manifestacoes do destinatario:")
    if not resultado.manifestacoes:
        linhas.append(
            "Nenhuma manifestacao localizada no historico sincronizado."
        )
    else:
        for idx, man in enumerate(resultado.manifestacoes):
            linhas.append(f"\u2713 {man.descricao}")
            linhas.append(f"  Data: {man.data}")
            linhas.append(f"  Protocolo do evento: {man.protocolo}")
            linhas.append(f"  NSU: {man.nsu}")
            if idx < len(resultado.manifestacoes) - 1:
                linhas.append("")

    if resultado.erro:
        linhas.append(f"Erro: {resultado.erro}")

    return "\n".join(linhas)
