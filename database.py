import sqlite3
import pandas as pd
from datetime import datetime
import json

DB_NAME = "hipotese_capital.db"

def conectar():
    return sqlite3.connect(DB_NAME)

def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()
    
    # TABELA 1: DADOS PERMANENTES (Características da Empresa)
    # O Ticker é a Primary Key (Chave Primária)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            ticker TEXT PRIMARY KEY,
            nome TEXT,
            setor_origem TEXT,
            industria_origem TEXT
        )
    ''')
    
    # TABELA 2: DADOS VARIÁVEIS (Histórico de Execuções)
    # O Ticker atua como Foreign Key (Chave Estrangeira)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            data_execucao TEXT,
            cotacao_atual REAL,
            p_l TEXT,
            sintese_ia TEXT,
            classificacao_b3 TEXT,
            FOREIGN KEY (ticker) REFERENCES empresas (ticker)
        )
    ''')
    conn.commit()
    conn.close()

def salvar_analise(ticker, d_cadastrais, d_mercado, relatorio):
    conn = conectar()
    cursor = conn.cursor()
    
    # 1. TRATA DADOS PERMANENTES (UPSERT)
    # Tenta inserir a empresa. Se já existir (IGNORE), não faz nada (não duplica dados fixos)
    cursor.execute('''
        INSERT OR IGNORE INTO empresas (ticker, nome, setor_origem, industria_origem)
        VALUES (?, ?, ?, ?)
    ''', (ticker, d_cadastrais.get('nome', 'N/D'), d_cadastrais.get('setor_origem', 'N/D'), d_cadastrais.get('industria_origem', 'N/D')))
    
    # 2. TRATA DADOS VARIÁVEIS (Nova linha sempre)
    # Garante que rodadas subsequentes não sobrescrevam dados anteriores (insere novo ID e Data)
    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Pegamos apenas a síntese geral das notícias para não poluir a tabela
    sintese_ia = relatorio.get('analise_noticias', {}).get('sintese_geral', 'N/D')
    classificacao_b3 = relatorio.get('classificacao_b3', 'N/D')
    
    cursor.execute('''
        INSERT INTO historico_analises (ticker, data_execucao, cotacao_atual, p_l, sintese_ia, classificacao_b3)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        ticker, 
        data_atual, 
        d_mercado.get('cotacao_atual', 0.0), 
        str(d_mercado.get('p_l', 'N/D')), 
        sintese_ia,
        classificacao_b3
    ))
    
    conn.commit()
    conn.close()

def buscar_historico():
    #Faz um JOIN das duas tabelas para exibir no Dashboard de forma amigável
    conn = conectar()
    
    query = '''
        SELECT 
            h.data_execucao as "Data da Análise",
            e.ticker as "Ativo",
            e.nome as "Empresa",
            h.cotacao_atual as "Cotação (R$)",
            h.p_l as "P/L",
            h.classificacao_b3 as "Classificação (B3)",
            h.sintese_ia as "Parecer da IA"
        FROM historico_analises h
        JOIN empresas e ON h.ticker = e.ticker
        ORDER BY h.data_execucao DESC
    '''
    
    # O Pandas já lê a query SQL e transforma num dicionário limpo para o Streamlit
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df.to_dict('records')