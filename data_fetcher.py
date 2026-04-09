import yfinance as yf
import feedparser
import urllib.parse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def buscar_dados_cadastrais(ticker: str) -> dict:
    """Busca dados cadastrais de forma robusta via Yahoo Finance."""
    ticker_sa = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
    
    try:
        info = yf.Ticker(ticker_sa).info
        return {
            "nome": info.get("shortName", "N/D"),
            "setor_origem": info.get("sector", "N/D"),
            "industria_origem": info.get("industry", "N/D"),
            "descricao_original": info.get("longBusinessSummary", "N/D"),
            "aviso": "Classificação B3 será inferida via IA a partir dos dados em inglês."
        }
    except Exception as e:
        logging.error(f"Erro cadastral para {ticker}: {e}")
        return {"erro": "Dados cadastrais indisponíveis."}

def buscar_dados_mercado(ticker: str) -> dict:
    """Busca cotação e indicadores fundamentalistas (Value Investing)."""
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
    """Busca as últimas notícias via Google News RSS."""
    try:
        query = urllib.parse.quote(f"{ticker} ações mercado financeiro brasil")
        url = f"https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        feed = feedparser.parse(url)
        noticias = []
        
        for entry in feed.entries[:limite]:
            noticias.append({
                "titulo": entry.title,
                "data": entry.published if hasattr(entry, 'published') else "N/D"
            })
            
        return noticias if noticias else [{"aviso": "Nenhuma notícia recente encontrada."}]
    except Exception as e:
        logging.error(f"Erro de notícias para {ticker}: {e}")
        return [{"erro": "Sistema de notícias temporariamente indisponível."}]