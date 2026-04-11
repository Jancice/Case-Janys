import yfinance as yf
import feedparser
import urllib.parse
import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# CONSTANTE GLOBAL: Simulação de navegador padronizada para todas as requisições
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def limpar_numero(texto):
    #Função auxiliar para limpar textos numéricos raspados da web.
    if not texto or str(texto).strip() in ['-', '', 'N/D', 'nan', 'None']:
        return "N/D"
    
    texto = str(texto).strip()
    is_pct = '%' in texto
    
    # Remove a percentagem, remove pontos de milhares e converte a vírgula em ponto decimal
    texto_limpo = texto.replace('%', '').replace('.', '').replace(',', '.').strip()
    
    try:
        val = float(texto_limpo)
        return val / 100.0 if is_pct else val
    except ValueError:
        return "N/D"

def buscar_dados_cadastrais(ticker: str) -> dict:
    #Busca Setor e Subsetor precisos via Web Scraping no Fundamentus, com fallback para o YFinance.
    ticker_limpo = ticker.upper().replace(".SA", "")
    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker_limpo}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status() 
        
        tabelas = pd.read_html(response.text)
        df_cadastral = tabelas[0]
        
        # Limpa a coluna 0 para remover o "?" e espaços extras que o site coloca
        df_cadastral[0] = df_cadastral[0].astype(str).str.replace('?', '', regex=False).str.strip()
        
        setor = df_cadastral[df_cadastral[0] == 'Setor'].iloc[0, 1] if not df_cadastral[df_cadastral[0] == 'Setor'].empty else "N/D"
        subsetor = df_cadastral[df_cadastral[0] == 'Subsetor'].iloc[0, 1] if not df_cadastral[df_cadastral[0] == 'Subsetor'].empty else "N/D"
        nome = df_cadastral[df_cadastral[0] == 'Empresa'].iloc[0, 1] if not df_cadastral[df_cadastral[0] == 'Empresa'].empty else "N/D"
        
        # Busca a descrição longa no Yahoo Finance
        ticker_sa = f"{ticker_limpo}.SA"
        try:
            info_yf = yf.Ticker(ticker_sa).info
            descricao = info_yf.get("longBusinessSummary", "N/D")
        except:
            descricao = "N/D"
            
        return {
            "nome": nome,
            "setor_origem": setor,
            "industria_origem": subsetor,
            "descricao_original": descricao,
            "aviso": "Classificação oficial da B3 extraída via Fundamentus."
        }
        
    except Exception as e:
        logging.warning(f"Erro ao acessar Fundamentus para {ticker}: {e}. Acionando Plano B (Yahoo Finance).")
        return buscar_dados_cadastrais_yfinance(ticker)
    
def buscar_dados_cadastrais_yfinance(ticker: str) -> dict:
    #Função de contingência (Fallback) caso o Fundamentus fique fora do ar.
    ticker_sa = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
    
    try:
        info = yf.Ticker(ticker_sa).info
        return {
            "nome": info.get("longName", info.get("shortName", "N/D")),
            "setor_origem": info.get("sector", "N/D"),
            "industria_origem": info.get("industry", "N/D"),
            "descricao_original": info.get("longBusinessSummary", "N/D"),
            "aviso": "Classificação B3 será inferida via IA a partir dos dados em inglês do Yahoo Finance."
        }
    except Exception as e:
        logging.error(f"Erro cadastral no Plano B para {ticker}: {e}")
        return {"erro": "Dados cadastrais indisponíveis em todas as fontes."}

def buscar_dados_mercado(ticker: str) -> dict:
    #Busca indicadores de mercado primariamente do Fundamentus e cruza com YF.
    ticker_limpo = ticker.upper().replace(".SA", "")
    ticker_sa = f"{ticker_limpo}.SA"

    dados_mercado = {
        "cotacao_atual": "N/D",
        "p_l": "N/D",
        "roe": "N/D",
        "margem_liquida": "N/D",
        "dividend_yield": "N/D",
        "divida_liquida_ebitda": "N/D"
    }

    ebitda = None
    try:
        info = yf.Ticker(ticker_sa).info
        ebitda = info.get("ebitda")
        # Fallback de segurança primário para cotação
        dados_mercado["cotacao_atual"] = info.get("currentPrice", "N/D")
    except Exception as e:
        logging.warning(f"Falha ao buscar EBITDA no YFinance para {ticker}: {e}")

    try:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker_limpo}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        dados_extraidos = {}
        
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            for i in range(0, len(cols) - 1, 2):
                chave = cols[i].get_text(strip=True).replace('?', '')
                valor = cols[i+1].get_text(strip=True)
                if chave:
                    dados_extraidos[chave] = valor

        dados_mercado["cotacao_atual"] = limpar_numero(dados_extraidos.get("Cotação", dados_mercado["cotacao_atual"]))
        dados_mercado["p_l"] = limpar_numero(dados_extraidos.get("P/L", "N/D"))
        dados_mercado["roe"] = limpar_numero(dados_extraidos.get("ROE", "N/D"))
        dados_mercado["margem_liquida"] = limpar_numero(dados_extraidos.get("Marg. Líquida", "N/D"))
        dados_mercado["dividend_yield"] = limpar_numero(dados_extraidos.get("Div. Yield", "N/D"))
        
        divida_liquida = "N/D"
        for k, v in dados_extraidos.items():
            if "Dív" in k and "Líq" in k and "EBITDA" not in k:
                divida_liquida = limpar_numero(v)
                break

        if divida_liquida != "N/D" and isinstance(ebitda, (int, float)) and ebitda != 0:
            dados_mercado["divida_liquida_ebitda"] = divida_liquida / ebitda
        else:
            div_ebitda_pronto = dados_extraidos.get("Dív.Líq/EBITDA", dados_extraidos.get("Div. Líq / EBITDA", "N/D"))
            dados_mercado["divida_liquida_ebitda"] = limpar_numero(div_ebitda_pronto)

    except Exception as e:
        logging.error(f"Falha na extração com BeautifulSoup para {ticker}: {e}")

    return dados_mercado

def buscar_noticias(ticker: str, limite: int = 5) -> list[dict]:
    #Busca as últimas notícias via Google News RSS.
    try:
        query = urllib.parse.quote(f"{ticker} ações mercado financeiro brasil")
        url = f"https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        feed = feedparser.parse(url)
        noticias = []
        
        for entry in feed.entries[:limite]:
            noticias.append({
                "titulo": entry.title,
                "data": entry.published if hasattr(entry, 'published') else "N/D",
                "link": entry.link
            })
            
        return noticias if noticias else [{"aviso": "Nenhuma notícia recente encontrada."}]
    except Exception as e:
        logging.error(f"Erro de notícias para {ticker}: {e}")
        return [{"erro": "Sistema de notícias temporariamente indisponível."}]