import streamlit as st
import pandas as pd
from data_fetcher import buscar_dados_cadastrais, buscar_dados_mercado, buscar_noticias
from ai_analyzer import gerar_relatorio_ia
import database as db

st.set_page_config(page_title="Hipótese Capital - IA", layout="wide")

# Garante que a tabela do banco exista ao iniciar o app
db.criar_tabela()

# --- FUNÇÃO DE FORMATAÇÃO DOS VALORS ---
def formatar_valor(valor, tipo="numero"):
    #Formata os números da API para o padrão de exibição visual BR.
    if pd.isna(valor) or valor in ["N/D", None, ""] or str(valor).strip() == "N/D":
        return "N/D"
    
    try:
        valor_float = float(valor)
    except (ValueError, TypeError):
        return str(valor)

    # Formatação padrão americano para manipulação de string: 1,000.00
    # O encadeamento de replace inverte para o padrão BR: 1.000,00
    if tipo == "moeda":
        return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
    elif tipo == "pct":
        return f"{(valor_float * 100):,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
        
    elif tipo in ["multiplo", "numero"]:
        # Removemos o 'x' do final e aplicamos a formatação limpa
        return f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
    return str(valor_float)
# -----------------------------------------------------------

@st.cache_data(show_spinner=False)
def coletar_dados_cacheados(ticker_selecionado):
    d_cad = buscar_dados_cadastrais(ticker_selecionado)
    d_mer = buscar_dados_mercado(ticker_selecionado)
    nots = buscar_noticias(ticker_selecionado)
    return d_cad, d_mer, nots

@st.cache_data(show_spinner=False)
def gerar_relatorio_cacheado(d_cad, d_mer, nots):
    # Só vai bater na API se esse conjunto exato de dados nunca tiver sido analisado
    return gerar_relatorio_ia(d_cad, d_mer, nots)


st.title("📊 Hipótese Capital - Briefing Semanal")
st.markdown("Protótipo de automação para o time de análise (Value Investing).")

# Barra superior de controles
col_select, col_btn = st.columns([3, 1])

with col_select:
    ticker_selecionado = st.text_input("Digite o ticker do ativo (ex: PETR4, VALE3):").strip().upper()

with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    gerar = st.button("Gerar Análise IA", use_container_width=True)

if gerar:
    if ticker_selecionado:
        with st.spinner(f"Extraindo dados e analisando {ticker_selecionado} (Buscando em cache se disponível)..."):
            
            # 1. Coleta (Cacheadas)
            d_cadastrais, d_mercado, noticias = coletar_dados_cacheados(ticker_selecionado)
            
            # TRATAMENTO DE ERRO: Ticker Inválido ou Deslistado (Fail-Fast)
            if d_mercado.get('cotacao_atual') == "N/D" and d_cadastrais.get('nome') == "N/D":
                st.error(f"O ativo **{ticker_selecionado}** não foi encontrado, é inválido ou foi deslistado da B3.")
                st.info("Verifique se o código está correto (ex: PETR4, VALE3) e tente novamente.")
                st.stop()
            
            # 2. Processamento IA (Cacheado)
            relatorio = gerar_relatorio_cacheado(d_cadastrais, d_mercado, noticias)
            
            st.success("Briefing gerado com sucesso!")
            
            # 3. Exibição e Salvamento
            if "erro" in relatorio:
                st.error(relatorio["erro"])
            else:
                db.salvar_analise(ticker_selecionado, d_cadastrais, d_mercado, relatorio)
                
                col_ia, col_dados = st.columns([2, 1])
                
                with col_ia:
                    nome_empresa = d_cadastrais.get('nome', 'Empresa Indisponível')
                    
                    st.markdown(f"<h1 style='color: #1E88E5;'>{nome_empresa} <span style='color: #6c757d; font-size: 0.6em;'>{ticker_selecionado}</span></h1>", unsafe_allow_html=True)
                    st.caption("Síntese executiva gerada por Inteligência Artificial")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    st.info(f"**Classificação B3:** {relatorio.get('classificacao_b3', 'N/D')} (Fundamentus)")
                    
                    st.subheader("Resumo do Negócio")
                    st.write(relatorio.get('resumo_negocio', 'N/D'))
                    
                    st.subheader("Análise de Fundamentos")
                    st.write(relatorio.get('interpretacao_indicadores', 'N/D'))
                    
                    st.subheader("Radar de Notícias")
                    
                    analise_noticias = relatorio.get('analise_noticias', {})
                    sintese = analise_noticias.get('sintese_geral', relatorio.get('sintese_geral', 'N/D'))
                    st.write(f"**Síntese:** {sintese}")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    lista_noticias = analise_noticias.get('classificacao_individual', [])
                    
                    if lista_noticias:
                        for noti in lista_noticias:
                            if isinstance(noti, dict):
                                sentimento = noti.get('sentimento', 'Neutro')
                                titulo = noti.get('titulo_noticia', 'N/D')
                                justificativa = noti.get('justificativa_breve', '')
                            elif isinstance(noti, str):
                                sentimento = 'Neutro'
                                titulo = noti
                                justificativa = ''
                            else:
                                continue
                                
                            if sentimento == "Positivo":
                                emoji = "🟢"
                            elif sentimento == "Negativo":
                                emoji = "🔴"
                            else:
                                emoji = "⚪"
                            
                            st.markdown(f"{emoji} **{titulo}**")
                            if justificativa:
                                st.caption(f"_{justificativa}_")
                            st.markdown("<br>", unsafe_allow_html=True)
                    else:
                        st.info("A IA não retornou classificação individual de notícias nesta análise.")
                        
                    st.subheader("Perguntas")
                    perguntas = relatorio.get('perguntas_investigacao', [])
                    for p in perguntas:
                        st.markdown(f"- {p}")
                        
                with col_dados:
                    st.header("🗄️ Dados Brutos Extraídos")
                    
                    with st.expander("📊 Dados de Mercado (Value Investing)", expanded=True):
                        c1, c2 = st.columns(2)
                        
                        c1.metric("Cotação Atual", formatar_valor(d_mercado.get('cotacao_atual'), "moeda"))
                        c2.metric("P/L", formatar_valor(d_mercado.get('p_l'), "numero"))
                        
                        c1.metric("ROE", formatar_valor(d_mercado.get('roe'), "pct"))
                        c2.metric("Margem Líquida", formatar_valor(d_mercado.get('margem_liquida'), "pct"))
                        
                        c1.metric("Dividend Yield", formatar_valor(d_mercado.get('dividend_yield'), "pct"))
                        c2.metric("Dívida Líq/EBITDA", formatar_valor(d_mercado.get('divida_liquida_ebitda'), "multiplo"))

                    with st.expander("📰 Últimas Notícias (RSS)", expanded=True):
                        if noticias and isinstance(noticias, list):
                            for noti in noticias:
                                titulo = noti.get('titulo', 'Notícia sem título')
                                data_pub = noti.get('data', 'Data desconhecida')
                                
                                st.markdown(f"**{titulo}**")
                                st.caption(f"📅 *Publicado em: {data_pub}*")
                                
                                if 'link' in noti:
                                    st.markdown(f"[🔗 Ler matéria completa]({noti['link']})")
                                st.divider()
                        else:
                            st.write("Nenhuma notícia recente encontrada no feed.")
    else:
        st.warning("Por favor, digite um ticker antes de gerar a análise.")

st.divider()
st.header("🗃️ Histórico do Banco de Dados")

historico = db.buscar_historico()
if historico:
    st.dataframe(pd.DataFrame(historico), use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma análise salva ainda. Pesquise um ativo acima para popular o banco!")