"""Gera um CSV com dados FICTÍCIOS de produção para testar o analisador.

Uso:
    python gerar_dados.py

Cria o arquivo dados_producao.csv com 30 dias de produção em 3 linhas e 2 turnos.
A Linha C foi feita propositalmente pior (mais refugo e mais paradas) para a IA
ter algo interessante para destacar no resumo.
"""
import random
from datetime import date, timedelta

import pandas as pd

random.seed(42)  # mesma semente = mesmos dados toda vez que rodar

LINHAS = {
    # linha: (produto, planejado por turno, eficiência mínima, eficiência máxima,
    #         taxa máxima de refugo, chance de parada)
    "Linha A": ("Tampa plástica", 500, 0.92, 0.99, 0.02, 0.15),
    "Linha B": ("Embalagem 500 ml", 450, 0.88, 0.97, 0.03, 0.20),
    "Linha C": ("Caixa organizadora", 400, 0.75, 0.93, 0.08, 0.45),
}
TURNOS = ["Manhã", "Tarde"]
MOTIVOS = [
    "Quebra de máquina",
    "Falta de material",
    "Setup / troca de ferramenta",
    "Manutenção preventiva",
    "Falta de operador",
]


def gerar(dias=30):
    inicio = date(2026, 10, 1)
    registros = []
    for i in range(dias):
        dia = inicio + timedelta(days=i)
        if dia.weekday() >= 5:  # pula sábado e domingo
            continue
        for linha, (produto, plan, ef_min, ef_max, refugo_max, p_parada) in LINHAS.items():
            for turno in TURNOS:
                produzido = int(plan * random.uniform(ef_min, ef_max))
                refugo = int(produzido * random.uniform(0, refugo_max))
                parou = random.random() < p_parada
                minutos = random.randint(10, 90) if parou else 0
                motivo = random.choice(MOTIVOS) if parou else ""
                registros.append(
                    {
                        "data": dia.isoformat(),
                        "linha": linha,
                        "turno": turno,
                        "produto": produto,
                        "pecas_planejadas": plan,
                        "pecas_produzidas": produzido,
                        "pecas_refugo": refugo,
                        "minutos_parada": minutos,
                        "motivo_parada": motivo,
                    }
                )
    return pd.DataFrame(registros)


if __name__ == "__main__":
    df = gerar()
    df.to_csv("dados_producao.csv", index=False)
    print(f"dados_producao.csv criado com {len(df)} registros.")
