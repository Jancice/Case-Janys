import streamlit as st
from data_fetcher import buscar_dados_cadastrais, buscar_dados_mercado, buscar_noticias
from ai_analyzer import gerar_relatorio_ia

# Tickers exigidos na Fase 1
TICKERS = ["ASAI3", "RECV3", "MOVI3", "BRKM5", "HBSA3", "ITUB4", "BBDC4", "OPCT3", "BRSR6", "PRIO3"]

st.set_page_config(page_title="Hipótese Capital - IA", layout="wide")


#@st.cache_data "Se o ticker for o mesmo, não rode a função de novo, use a memória"

@st.cache_data(show_spinner=False)
def coletar_dados_cacheados(ticker_selecionado):
    d_cad = buscar_dados_cadastrais(ticker_selecionado)
    d_mer = buscar_dados_mercado(ticker_selecionado)
    nots = buscar_noticias(ticker_selecionado)
    return d_cad, d_mer, nots

@st.cache_data(show_spinner=False)
def gerar_relatorio_cacheado(d_cad, d_mer, nots):
    return gerar_relatorio_ia(d_cad, d_mer, nots)


st.title("📊 Hipótese Capital - Briefing Semanal")
st.markdown("Protótipo de automação para o time de análise (Value Investing).")

# Barra superior de controles
col_select, col_btn = st.columns([3, 1])
with col_select:
    ticker = st.selectbox("Selecione o ativo para análise:", TICKERS)
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    gerar = st.button("Gerar Análise IA", use_container_width=True)

if gerar:
    with st.spinner(f"Extraindo dados e analisando {ticker} (Buscando em cache se disponível)..."):
        
        # 1. Coleta
        d_cadastrais, d_mercado, noticias = coletar_dados_cacheados(ticker)
        
        # 2. Processamento IA
        relatorio = gerar_relatorio_cacheado(d_cadastrais, d_mercado, noticias)
        
        st.success("Briefing gerado com sucesso!")
        st.divider()
        
        # 3. Exibição
        if "erro" in relatorio:
            st.error(relatorio["erro"])
        else:
            col_ia, col_dados = st.columns([2, 1])
            
            with col_ia:
                # 1. Resgata o nome da empresa dos dados extraídos
                nome_empresa = d_cadastrais.get('nome', 'Empresa Indisponível')
                
                # 2. Cria um título visualmente muito mais atrativo usando Markdown
                st.markdown(f"<h1 style='color: #1E88E5;'>{nome_empresa} <span style='color: #6c757d; font-size: 0.6em;'>{ticker}</span></h1>", unsafe_allow_html=True)
                st.caption("Síntese executiva gerada por Inteligência Artificial")
                st.markdown("<br>", unsafe_allow_html=True)
                
                # 3. Mantém a info da B3
                st.info(f"**Classificação B3:** {relatorio.get('classificacao_b3', 'N/D')} (Fundamentus)")
                
                st.subheader("Resumo do Negócio")
                st.write(relatorio.get('resumo_negocio', 'N/D'))
                
                st.subheader("Análise de Fundamentos")
                st.write(relatorio.get('interpretacao_indicadores', 'N/D'))
                
                st.subheader("Radar de Notícias")
                
                # Resgata o novo objeto de notícias (usa um dict vazio como fallback se não achar)
                analise_noticias = relatorio.get('analise_noticias', {})
                
                if analise_noticias:
                    # Exibe a síntese geral primeiro
                    st.write(f"**Síntese:** {analise_noticias.get('sintese_geral', 'N/D')}")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Percorre a lista de notícias classificadas individualmente
                    for noti in analise_noticias.get('classificacao_individual', []):
                        sentimento = noti.get('sentimento', 'Neutro')
                        
                        # Define o emoji de acordo com o sentimento retornado pela IA
                        if sentimento == "Positivo":
                            emoji = "🟢"
                        elif sentimento == "Negativo":
                            emoji = "🔴"
                        else:
                            emoji = "⚪"
                        
                        # Desenha o Título com Emoji e a Justificativa em texto menor (caption)
                        st.markdown(f"{emoji} **{noti.get('titulo_noticia', 'N/D')}**")
                        st.caption(f"_{noti.get('justificativa_breve', '')}_")
                        st.markdown("<br>", unsafe_allow_html=True)
                else:
                    # Fallback caso a IA tenha falhado no formato
                    st.write(relatorio.get('sintese_noticias', 'Erro ao processar as notícias.'))
                
                st.subheader("Perguntas para Investigação")
                perguntas = relatorio.get('perguntas_investigacao', [])
                for p in perguntas:
                    st.markdown(f"- {p}")
                    
            with col_dados:
                st.header(" Dados Brutos Extraídos")
                
                with st.expander("📊 Dados de Mercado (Value Investing)", expanded=True):
                    # Função auxiliar para formatar os números adequadamente (Pt-BR)
                    def formatar_valor(val, formato="numero"):
                        if not isinstance(val, (int, float)): 
                            return "N/D"
                        
                        if formato == "moeda":
                            return f"R$ {val:.2f}".replace(".", ",")
                        elif formato == "pct":
                            return f"{(val * 100):.2f}%".replace(".", ",")
                        elif formato == "multiplo":
                            return f"{val:.2f}x".replace(".", ",")
                        else:
                            return f"{val:.2f}".replace(".", ",")

                    # Dividindo em duas colunas para um visual mais limpo
                    c1, c2 = st.columns(2)
                    
                    c1.metric("Cotação Atual", formatar_valor(d_mercado.get('cotacao_atual'), "moeda"))
                    c2.metric("P/L", formatar_valor(d_mercado.get('p_l'), "numero"))
                    
                    c1.metric("ROE", formatar_valor(d_mercado.get('roe'), "pct"))
                    c2.metric("Margem Líquida", formatar_valor(d_mercado.get('margem_liquida'), "pct"))
                    
                    c1.metric("Dividend Yield", formatar_valor(d_mercado.get('dividend_yield'), "pct"))
                    c2.metric("Dívida Líq/EBITDA", formatar_valor(d_mercado.get('divida_liquida_ebitda'), "multiplo"))

                with st.expander(" Últimas Notícias (RSS)", expanded=True):
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