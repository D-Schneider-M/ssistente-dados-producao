"""Ferramentas de análise que o agente de IA pode chamar.

A IA NÃO lê o CSV nem faz conta. Ela decide qual ferramenta chamar e com quais
parâmetros; quem calcula é o pandas, aqui. Todas as ferramentas só LEEM os dados
(nada é alterado nem executado a partir de texto da IA).

Definições usadas em todo o projeto:
    eficiência = peças produzidas / peças planejadas
    refugo %   = peças de refugo / peças produzidas
"""
import pandas as pd

COLUNAS = [
    "data", "linha", "turno", "produto", "pecas_planejadas",
    "pecas_produzidas", "pecas_refugo", "minutos_parada", "motivo_parada",
]
AGRUPAMENTOS = ("linha", "turno", "produto", "semana")
METRICAS_DIAS = ("eficiencia", "refugo", "paradas")


# ----------------------------------------------------------------- dados
def carregar_dados(origem):
    """Lê o CSV (caminho ou arquivo enviado) e valida as colunas."""
    df = pd.read_csv(origem, parse_dates=["data"])
    faltando = [c for c in COLUNAS if c not in df.columns]
    if faltando:
        raise ValueError("Colunas faltando no CSV: " + ", ".join(faltando))
    df["motivo_parada"] = df["motivo_parada"].fillna("")
    return df


def _igual(serie, valor):
    """Comparação sem diferenciar maiúsculas; aceita 'A' para 'Linha A'."""
    valor = valor.strip().lower()
    s = serie.str.lower()
    return (s == valor) | s.str.endswith(" " + valor)


def filtrar(df, linha="", turno="", data_inicio="", data_fim=""):
    """Aplica os filtros opcionais. Lança ValueError se nada sobrar."""
    out = df
    if linha:
        out = out[_igual(out["linha"], linha)]
    if turno:
        out = out[_igual(out["turno"], turno)]
    if data_inicio:
        out = out[out["data"] >= pd.to_datetime(data_inicio)]
    if data_fim:
        out = out[out["data"] <= pd.to_datetime(data_fim)]
    if out.empty:
        raise ValueError(
            "Nenhum registro para esse filtro. "
            f"Linhas: {sorted(df['linha'].unique())}; turnos: {sorted(df['turno'].unique())}; "
            f"período: {df['data'].min():%Y-%m-%d} a {df['data'].max():%Y-%m-%d}."
        )
    return out


# ----------------------------------------------------------------- cálculos
def _pct(numerador, denominador):
    return round(float(100 * numerador / denominador), 2) if denominador else None


def _resumo(parte):
    planejado = int(parte["pecas_planejadas"].sum())
    produzido = int(parte["pecas_produzidas"].sum())
    refugo = int(parte["pecas_refugo"].sum())
    return {
        "pecas_planejadas": planejado,
        "pecas_produzidas": produzido,
        "eficiencia_pct": _pct(produzido, planejado),
        "pecas_refugo": refugo,
        "refugo_pct": _pct(refugo, produzido),
        "minutos_parada": int(parte["minutos_parada"].sum()),
        "ocorrencias_de_parada": int((parte["minutos_parada"] > 0).sum()),
    }


def visao_geral(df):
    """Totais do recorte e o que existe nos dados."""
    resumo = _resumo(df)
    resumo.update(
        {
            "periodo": f"{df['data'].min():%Y-%m-%d} a {df['data'].max():%Y-%m-%d}",
            "linhas": sorted(df["linha"].unique().tolist()),
            "turnos": sorted(df["turno"].unique().tolist()),
            "produtos": sorted(df["produto"].unique().tolist()),
            "registros": int(len(df)),
        }
    )
    return resumo


def indicadores_por_grupo(df, agrupar_por):
    """Indicadores agrupados por linha, turno, produto ou semana."""
    if agrupar_por not in AGRUPAMENTOS:
        raise ValueError(f"agrupar_por deve ser um de {AGRUPAMENTOS}")
    base = df.copy()
    if agrupar_por == "semana":
        base["semana"] = base["data"].dt.to_period("W").dt.start_time.dt.strftime("%Y-%m-%d")
    linhas = []
    for nome, parte in base.groupby(agrupar_por):
        item = {agrupar_por: nome}
        item.update(_resumo(parte))
        linhas.append(item)
    return linhas


def pareto_paradas(df):
    """Minutos parados por motivo, do maior para o menor, com % acumulado."""
    paradas = df[(df["minutos_parada"] > 0) & (df["motivo_parada"] != "")]
    if paradas.empty:
        return []
    por_motivo = (
        paradas.groupby("motivo_parada")["minutos_parada"].sum().sort_values(ascending=False)
    )
    total = por_motivo.sum()
    acumulado = 0
    linhas = []
    for motivo, minutos in por_motivo.items():
        acumulado += minutos
        linhas.append(
            {
                "motivo": motivo,
                "minutos": int(minutos),
                "pct": _pct(minutos, total),
                "pct_acumulado": _pct(acumulado, total),
            }
        )
    return linhas


def piores_dias(df, metrica, quantidade=5):
    """Dias mais problemáticos: menor eficiência, maior refugo ou mais paradas."""
    if metrica not in METRICAS_DIAS:
        raise ValueError(f"metrica deve ser uma de {METRICAS_DIAS}")
    quantidade = max(1, min(int(quantidade), 10))
    dias = []
    for dia, parte in df.groupby("data"):
        item = {"data": f"{dia:%Y-%m-%d}"}
        item.update(_resumo(parte))
        dias.append(item)
    campo, pior_e_menor = {
        "eficiencia": ("eficiencia_pct", True),
        "refugo": ("refugo_pct", False),
        "paradas": ("minutos_parada", False),
    }[metrica]
    dias.sort(key=lambda d: d[campo], reverse=not pior_e_menor)
    return dias[:quantidade]


# ----------------------------------------------------------------- ferramentas do agente
def _executar(log, nome, argumentos, funcao):
    """Roda a função, devolve sempre um dict e registra a chamada (para mostrar na tela)."""
    argumentos = {k: v for k, v in argumentos.items() if v not in ("", None)}
    try:
        resultado = {"dados": funcao()}
    except Exception as erro:  # a IA recebe o erro e pode corrigir os parâmetros
        resultado = {"erro": f"{type(erro).__name__}: {erro}"}
    log.append({"ferramenta": nome, "argumentos": argumentos, "resultado": resultado})
    return resultado


def criar_ferramentas(df, log):
    """Devolve as funções que serão entregues ao Gemini (function calling).

    As docstrings são importantes: é por elas que a IA entende quando usar cada ferramenta.
    """

    def consultar_visao_geral(
        linha: str = "", turno: str = "", data_inicio: str = "", data_fim: str = ""
    ) -> dict:
        """Totais gerais (peças, eficiência, refugo, paradas) e o que existe nos dados
        (período, linhas, turnos, produtos). Use primeiro para se orientar.
        Todos os parâmetros são opcionais; deixe vazio para considerar tudo.
        Datas no formato AAAA-MM-DD. linha ex.: 'Linha A'. turno: 'Manhã' ou 'Tarde'."""
        args = dict(linha=linha, turno=turno, data_inicio=data_inicio, data_fim=data_fim)
        return _executar(log, "consultar_visao_geral", args,
                         lambda: visao_geral(filtrar(df, **args)))

    def consultar_indicadores(
        agrupar_por: str, linha: str = "", turno: str = "",
        data_inicio: str = "", data_fim: str = "",
    ) -> dict:
        """Indicadores de eficiência, refugo e paradas agrupados.
        agrupar_por: 'linha', 'turno', 'produto' ou 'semana' (obrigatório).
        Os demais parâmetros são filtros opcionais; deixe vazio para considerar tudo.
        Datas no formato AAAA-MM-DD."""
        args = dict(agrupar_por=agrupar_por, linha=linha, turno=turno,
                    data_inicio=data_inicio, data_fim=data_fim)
        filtros = dict(linha=linha, turno=turno, data_inicio=data_inicio, data_fim=data_fim)
        return _executar(log, "consultar_indicadores", args,
                         lambda: indicadores_por_grupo(filtrar(df, **filtros), agrupar_por))

    def consultar_pareto_paradas(
        linha: str = "", turno: str = "", data_inicio: str = "", data_fim: str = ""
    ) -> dict:
        """Pareto das paradas: minutos parados por motivo, do maior para o menor,
        com percentual e percentual acumulado. Filtros opcionais; deixe vazio para tudo.
        Datas no formato AAAA-MM-DD."""
        args = dict(linha=linha, turno=turno, data_inicio=data_inicio, data_fim=data_fim)
        return _executar(log, "consultar_pareto_paradas", args,
                         lambda: pareto_paradas(filtrar(df, **args)))

    def consultar_piores_dias(
        metrica: str, quantidade: int = 5, linha: str = "", turno: str = ""
    ) -> dict:
        """Dias mais problemáticos. metrica: 'eficiencia' (menores), 'refugo' (maiores)
        ou 'paradas' (mais minutos parados). quantidade: de 1 a 10. Filtros opcionais."""
        args = dict(metrica=metrica, quantidade=quantidade, linha=linha, turno=turno)
        filtros = dict(linha=linha, turno=turno)
        return _executar(log, "consultar_piores_dias", args,
                         lambda: piores_dias(filtrar(df, **filtros), metrica, quantidade))

    return [consultar_visao_geral, consultar_indicadores,
            consultar_pareto_paradas, consultar_piores_dias]
