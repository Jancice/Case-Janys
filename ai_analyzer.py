import json
import os
from groq import Groq
from dotenv import load_dotenv

# Carrega o .env e inicializa o cliente Groq
load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def gerar_relatorio_ia(dados_cadastrais: dict, dados_mercado: dict, noticias: list) -> dict:
    """Envia os dados para a IA via Groq (Llama 3) e força a saída em JSON."""
    
    prompt = f"""
    Você é um Analista de Ações Sênior na gestora Hipótese Capital (foco em Value Investing).
    Sua tese exige alta convicção, proteção de downside e foco na qualidade do negócio.
    
    DADOS DE MERCADO: {json.dumps(dados_mercado, ensure_ascii=False)}
    DADOS CADASTRAIS: {json.dumps(dados_cadastrais, ensure_ascii=False)}
    NOTÍCIAS RECENTES: {json.dumps(noticias, ensure_ascii=False)}
    
    INSTRUÇÕES CRÍTICAS:
    1. CLASSIFICAÇÃO: Utilize os campos 'setor_origem' e 'industria_origem' fornecidos nos DADOS CADASTRAIS para compor a taxonomia. Não tente adivinhar ou traduzir.
    2. Seja analítico, cético e não faça recomendações explícitas de compra/venda.
    3. Retorne APENAS um objeto JSON válido, sem texto adicional.
    
    Você DEVE retornar um objeto JSON com as seguintes chaves exatas:
    - "classificacao_b3": (string) Formato exigido: "Setor: [setor_origem] / Subsetor: [industria_origem]".
    - "resumo_negocio": (string) Resumo da empresa e vantagens competitivas em português, baseado na 'descricao_original'.
    - "interpretacao_indicadores": (string) Análise cética dos indicadores de Value Investing fornecidos.
    - "analise_noticias": (objeto) Contendo duas chaves:
        - "classificacao_individual": (lista de objetos) Para cada notícia, crie um objeto com: "titulo_noticia" (string), "sentimento" (string com EXATAMENTE "Positivo", "Negativo" ou "Neutro") e "justificativa_breve" (string de 4 linhas bem formatadadas, explicando o impacto).
        - "sintese_geral": (string) Resumo de um parágrafo, formatado, linhas do impacto desse bloco de notícias na tese.
    - "perguntas_investigacao": (lista de strings) Exatas 3 perguntas críticas que relacionem as noticias e informações coletadas sobre o ativo que o investidor deveria investigar antes de tomar uma decisão.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é uma API de processamento de dados financeiros. Você deve responder estritamente com um JSON válido e nada mais."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        resposta_texto = chat_completion.choices[0].message.content
        return json.loads(resposta_texto)
        
    except Exception as e:
        return {"erro": f"Falha na IA do Groq: {str(e)}"}