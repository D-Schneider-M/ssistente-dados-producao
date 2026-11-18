# Assistente de Dados de Produção com IA

Agente de IA (Gemini) que responde, em português, perguntas sobre dados de produção industrial, como "qual o principal motivo de parada da Linha C?". Os números vêm de funções em pandas, e não da "cabeça" do modelo, então a IA não inventa valores.

**App online:** _(cole aqui o link do Streamlit depois de publicar)_

> Os dados do exemplo são **fictícios**, gerados por `gerar_dados.py`.

## Como funciona

O projeto usa **function calling**: a IA não lê o CSV, ela escolhe qual ferramenta chamar.

1. Você faz uma pergunta no chat (interface em **Streamlit**).
2. O Gemini recebe a pergunta e a lista de ferramentas disponíveis (`ferramentas.py`).
3. Ele pede para chamar uma delas, por exemplo `consultar_pareto_paradas(linha="Linha C")`.
4. O código Python executa a função com pandas e devolve os números.
5. O Gemini escreve a resposta final com esses números. A tela mostra quais ferramentas foram usadas.

As ferramentas só **leem** os dados: nenhum código gerado pela IA é executado.

| Arquivo | Função |
|---|---|
| `app.py` | Interface: aba de chat e aba de painel (indicadores e Pareto) |
| `agente.py` | Agente: conexão com a API do Gemini, instruções e tentativas automáticas |
| `ferramentas.py` | Cálculos em pandas: visão geral, indicadores por grupo, Pareto de paradas, piores dias |
| `gerar_dados.py` | Gera dados fictícios de produção (3 linhas, 2 turnos) |

## Como rodar

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Para ativar o agente, crie um arquivo `.env` na pasta com sua chave do Google AI Studio:

```
GEMINI_API_KEY=cole_sua_chave_aqui
```

Sem a chave, o painel funciona normalmente e o chat fica desativado. Se aparecer erro de modelo não encontrado, defina `GEMINI_MODEL=nome_do_modelo` no `.env`.

Você pode enviar seu próprio CSV pela barra lateral. Colunas necessárias: `data, linha, turno, produto, pecas_planejadas, pecas_produzidas, pecas_refugo, minutos_parada, motivo_parada`.

## Perguntas de exemplo

- Qual linha tem a pior eficiência?
- Qual o principal motivo de parada da Linha C?
- Como o refugo evoluiu semana a semana?
- Quais foram os 3 piores dias de eficiência?
- Compare os turnos da manhã e da tarde.

## Definições

- Eficiência = peças produzidas ÷ peças planejadas
- Refugo % = peças de refugo ÷ peças produzidas

## Tecnologias

Python, pandas, Streamlit, API do Gemini (google-genai, function calling).

## Possíveis melhorias

- Mais ferramentas (custo por peça, OEE completo)
- Gráficos gerados a partir das respostas do agente
- Leitura direta de planilhas Excel
