"""Agente de IA: conversa em português e usa as ferramentas para responder com números reais.

Como funciona (function calling):
    1. Você faz uma pergunta.
    2. O Gemini recebe a pergunta + a lista de ferramentas (nome, parâmetros, descrição).
    3. Em vez de responder, ele devolve "quero chamar consultar_pareto_paradas(linha='Linha C')".
    4. O SDK executa essa função (código nosso, em ferramentas.py) e devolve o resultado ao Gemini.
    5. O Gemini escreve a resposta final usando os números recebidos.
O SDK faz os passos 3 a 5 automaticamente (automatic function calling).
"""
import os
import re
import time

from google import genai
from google.genai import types

from ferramentas import criar_ferramentas

# Se der "modelo não encontrado", troque pelo nome atual no Google AI Studio
# (ou defina GEMINI_MODEL no arquivo .env).
MODELO = os.getenv("GEMINI_MODEL", "gemini-4-hydrogen")

INSTRUCOES = """Você é um assistente de análise de dados de produção industrial, para engenheiros
e gestores. Responda sempre em português do Brasil.

Regras:
- Para qualquer número, use SEMPRE as ferramentas. Nunca invente nem estime valores.
- Se a pergunta não for sobre os dados de produção, diga que só responde sobre eles.
- Se uma ferramenta devolver erro, corrija os parâmetros e tente de novo.
- Cite a linha e o período a que os números se referem.
- Eficiência = produzido / planejado. Refugo % = refugo / produzido.
- Seja direto: até cerca de 120 palavras. Quando fizer sentido, termine com uma
  recomendação prática de melhoria."""


NUMERO = re.compile(r"\d")
COBRANCA = (
    "Você respondeu sem consultar as ferramentas, então esses números não são confiáveis. "
    "Chame as ferramentas disponíveis para consultar os dados e responda de novo, "
    "usando apenas os números que elas retornarem."
)
SEM_CONSULTA = (
    "Não consegui consultar os dados para responder com segurança, e prefiro não "
    "mostrar números sem checagem. Tente reformular a pergunta ou clique em Nova conversa."
)


class AgenteProducao:
    def __init__(self, df, api_key, modelo=MODELO):
        self.log = []  # registro das ferramentas chamadas, para mostrar na tela
        # O cliente precisa ficar guardado em self: se ele sair de escopo, o Python o descarta
        # e a conexão é fechada ("o cliente foi fechado").
        self.cliente = genai.Client(api_key=api_key)
        self.chat = self.cliente.chats.create(
            model=modelo,
            config=types.GenerateContentConfig(
                system_instruction=INSTRUCOES,
                tools=criar_ferramentas(df, self.log),
            ),
        )

    def _enviar(self, mensagem):
        """Envia uma mensagem ao Gemini, com tentativas automáticas."""
        for tentativa in range(1, 4):
            self.log.clear()
            try:
                resposta = self.chat.send_message(mensagem)
                return resposta.text or "", list(self.log)
            except Exception:
                if tentativa == 3:
                    raise
                time.sleep(5 * tentativa)  # erros 503 (modelo ocupado) costumam passar

    def perguntar(self, pergunta):
        """Devolve (texto da resposta, lista de ferramentas usadas).

        Trava anti-invenção: resposta com números e SEM nenhuma consulta às ferramentas
        é descartada. O agente é cobrado até 2 vezes; se mesmo assim não consultar os
        dados, o usuário recebe um aviso em vez de números inventados.
        """
        texto, consultas = self._enviar(pergunta)
        for _ in range(2):
            if consultas or not NUMERO.search(texto):
                return texto or "Não consegui gerar uma resposta.", consultas
            texto, consultas = self._enviar(COBRANCA)
        if consultas or not NUMERO.search(texto):
            return texto or "Não consegui gerar uma resposta.", consultas
        return SEM_CONSULTA, []
