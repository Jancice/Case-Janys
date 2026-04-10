import yfinance as yf
import feedparser
import urllib.parse
import logging
import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def buscar_dados_cadastrais(ticker: str) -> dict:
    #Busca Setor e Subsetor precisos via Web Scraping no Fundamentus, com fallback para o YFinance.
    
    # O Fundamentus não usa o sufixo .SA nas URLs (necessario tirar)
    ticker_limpo = ticker.upper().replace(".SA", "")
    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker_limpo}"
    
    # Headers mais robustos para simular um navegador real e não ser bloqueado
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 
        
        tabelas = pd.read_html(response.text)
        df_cadastral = tabelas[0]
        
        #solução do problema do webscrapping: o caractere '?' estava atrapalhando a busca exata.
        df_cadastral[0] = df_cadastral[0].astype(str).str.replace('?', '', regex=False).str.strip()
        
        # Agora a busca no fundamentus vai funcionar
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
    # Busca cotação e indicadores (Value Investing).
    ticker_sa = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
    
    try:
        info = yf.Ticker(ticker_sa).info
        return {
            "cotacao_atual": info.get("currentPrice", info.get("regularMarketPrice", "N/D")),
            "p_l": info.get("trailingPE", "N/D"),
            "roe": info.get("returnOnEquity", "N/D"),
            "margem_liquida": info.get("profitMargins", "N/D"),
            "dividend_yield": info.get("dividendYield", "N/D"),
            "divida_liquida_ebitda": info.get("enterpriseToEbitda", "N/D") 
        }
    except Exception as e:
        logging.error(f"Erro de mercado para {ticker}: {e}")
        return {"erro": "Dados de mercado indisponíveis."}

def buscar_noticias(ticker: str, limite: int = 5) -> list[dict]:
    # Busca as últimas notícias via Google News RSS.
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