"""Interface (Streamlit) do Assistente de Dados de Produção com IA.

Rodar:  python -m streamlit run app.py
"""
import io
import os
import traceback

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()  # lê GEMINI_API_KEY do arquivo .env (uso local)
except ImportError:
    pass

from ferramentas import carregar_dados, indicadores_por_grupo, pareto_paradas, visao_geral

st.set_page_config(page_title="Assistente de Produção com IA", page_icon="🏭", layout="wide")

ARQUIVO_PADRAO = "dados_producao.csv"
LIMITE_PERGUNTAS = 20  # protege a cota da chave quando o app está publicado
EXEMPLOS = [
    "Qual linha tem a pior eficiência?",
    "Qual o principal motivo de parada da Linha C?",
    "Como o refugo evoluiu semana a semana?",
    "Quais foram os 3 piores dias de eficiência?",
]


def obter_chave():
    """Chave local (.env) ou, quando publicado, a configurada nos Secrets do Streamlit."""
    chave = os.getenv("GEMINI_API_KEY")
    if chave:
        return chave
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None


# ----------------------------------------------------------------- dados (barra lateral)
with st.sidebar:
    st.header("Dados")
    enviado = st.file_uploader("Use seu próprio CSV (opcional)", type="csv")
    st.caption(
        "Sem upload, o app usa dados **fictícios** de 3 linhas de produção. "
        "O CSV precisa ter as colunas: data, linha, turno, produto, pecas_planejadas, "
        "pecas_produzidas, pecas_refugo, minutos_parada, motivo_parada."
    )

try:
    if enviado is not None:
        df = carregar_dados(io.BytesIO(enviado.getvalue()))
        fonte = enviado.name
    else:
        df = carregar_dados(ARQUIVO_PADRAO)
        fonte = ARQUIVO_PADRAO
except Exception as erro:
    st.error(f"Não consegui ler os dados: {erro}")
    st.stop()

st.title("🏭 Assistente de Produção com IA")
st.caption(f"Dados: {fonte} • {len(df)} registros • agente Gemini com function calling")

aba_chat, aba_painel = st.tabs(["💬 Assistente", "📊 Painel"])

# ----------------------------------------------------------------- painel
with aba_painel:
    geral = visao_geral(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eficiência geral", f"{geral['eficiencia_pct']}%")
    c2.metric("Refugo geral", f"{geral['refugo_pct']}%")
    c3.metric("Minutos parados", f"{geral['minutos_parada']}")
    c4.metric("Período", geral["periodo"])

    st.subheader("Indicadores por linha")
    tabela = pd.DataFrame(indicadores_por_grupo(df, "linha")).set_index("linha")
    st.dataframe(
        tabela[["eficiencia_pct", "refugo_pct", "minutos_parada", "ocorrencias_de_parada"]],
    )

    st.subheader("Pareto das paradas (minutos por motivo)")
    pareto = pd.DataFrame(pareto_paradas(df))
    if pareto.empty:
        st.info("Não há paradas registradas.")
    else:
        st.bar_chart(pareto.set_index("motivo")["minutos"])
        st.dataframe(pareto, hide_index=True)

# ----------------------------------------------------------------- assistente
with aba_chat:
    chave = obter_chave()
    if not chave:
        st.warning(
            "Chave da API não configurada. Crie um arquivo `.env` com "
            "`GEMINI_API_KEY=sua_chave` (veja o README). O painel funciona sem a chave."
        )

    # Um agente novo para cada conjunto de dados (a conversa recomeça se o CSV mudar).
    assinatura = (fonte, len(df))
    if st.session_state.get("assinatura") != assinatura:
        st.session_state.assinatura = assinatura
        st.session_state.mensagens = []
        st.session_state.usadas = 0
        st.session_state.agente = None

    if st.button("🔄 Nova conversa"):  # descarta o agente atual e recomeça do zero
        st.session_state.mensagens = []
        st.session_state.agente = None

    if chave and st.session_state.agente is None:
        from agente import AgenteProducao  # importa só quando há chave

        st.session_state.agente = AgenteProducao(df, chave)

    st.write("Experimente uma pergunta:")
    colunas = st.columns(len(EXEMPLOS))
    clicada = None
    for coluna, exemplo in zip(colunas, EXEMPLOS):
        if coluna.button(exemplo, disabled=not chave):
            clicada = exemplo

    for msg in st.session_state.mensagens:
        with st.chat_message(msg["papel"]):
            st.markdown(msg["texto"])
            if msg.get("consultas"):
                with st.expander("Como o agente chegou a essa resposta"):
                    for consulta in msg["consultas"]:
                        st.markdown(f"**{consulta['ferramenta']}**")
                        st.json(consulta["argumentos"])

    pergunta = st.chat_input("Pergunte sobre os dados de produção...", disabled=not chave) or clicada

    if pergunta:
        with st.chat_message("user"):
            st.markdown(pergunta)
        st.session_state.mensagens.append({"papel": "user", "texto": pergunta})

        with st.chat_message("assistant"):
            if st.session_state.usadas >= LIMITE_PERGUNTAS:
                texto, consultas = (
                    f"Limite de {LIMITE_PERGUNTAS} perguntas por sessão atingido. "
                    "Recarregue a página para recomeçar.",
                    [],
                )
                st.markdown(texto)
            else:
                try:
                    with st.spinner("Consultando os dados..."):
                        texto, consultas = st.session_state.agente.perguntar(pergunta)
                    st.session_state.usadas += 1
                    st.markdown(texto)
                    if consultas:
                        with st.expander("Como o agente chegou a essa resposta"):
                            for consulta in consultas:
                                st.markdown(f"**{consulta['ferramenta']}**")
                                st.json(consulta["argumentos"])
                except Exception as erro:
                    print(traceback.format_exc())  # o detalhe completo aparece no terminal
                    st.session_state.agente = None  # a próxima pergunta cria um agente novo
                    texto, consultas = f"Não consegui responder agora. Detalhe: {erro}", []
                    st.error(texto)
        st.session_state.mensagens.append(
            {"papel": "assistant", "texto": texto, "consultas": consultas}
        )
