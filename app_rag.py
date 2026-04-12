import streamlit as st
import chromadb
import os
import re
from groq import Groq
from dotenv import load_dotenv

# CONFIGURAÇÕES GERAIS
PASTA_DADOS = "dados_empresa"
st.set_page_config(page_title="RAG - Pipeline Completo", layout="wide")

@st.cache_resource
def inicializar_conexoes():
    load_dotenv()
    try:
        cliente_llm = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    except:
        st.error("Erro na API Key.")
        st.stop()
    
    cliente_chroma = chromadb.PersistentClient(path="./banco_vetorial_simples")
    colecao = cliente_chroma.get_or_create_collection(name="memoria_institucional")
    return cliente_llm, colecao

cliente_llm, colecao = inicializar_conexoes()

# MOTOR DE ETL (EXTRAÇÃO E ENRIQUECIMENTO)
def extrair_metadados(texto):
    #Extrai Ano e tenta deduzir o Setor principal do texto.
    # Extrai o ano (primeiro que achar)
    anos = re.findall(r'\b(19\d{2}|20\d{2})\b', texto)
    ano_doc = int(anos[0]) if anos else 1900
    
    # Extrai setor com base em palavras-chave simples
    texto_lower = texto.lower()
    if "energia" in texto_lower or "elétrico" in texto_lower or "transmissão" in texto_lower:
        setor = "Energia"
    elif "saneamento" in texto_lower or "água" in texto_lower:
        setor = "Saneamento"
    else:
        setor = "Geral"
        
    return ano_doc, setor

def fragmentar_texto(texto, max_palavras=150):
    #Fatia textos longos em pedaços menores (Chunks) para a vetorização.
    palavras = texto.split()
    chunks = []
    for i in range(0, len(palavras), max_palavras):
        chunk = " ".join(palavras[i:i + max_palavras])
        chunks.append(chunk)
    return chunks

# BARRA LATERAL (INGESTÃO DE DADOS)
with st.sidebar:
    st.header("⚙️ Pipeline de Ingestão")
    if st.button("Processar Documentos (ETL)", use_container_width=True):
        if os.path.exists(PASTA_DADOS):
            arquivos = [f for f in os.listdir(PASTA_DADOS) if f.endswith('.txt')]
            total_chunks = 0
            
            with st.spinner("Extraindo, Limpando, Fatiando e Vetorizando..."):
                for arquivo in arquivos:
                    with open(os.path.join(PASTA_DADOS, arquivo), 'r', encoding='utf-8') as f:
                        conteudo_bruto = f.read()
                    
                    # 1 e 2. Extração de Metadados
                    ano, setor = extrair_metadados(conteudo_bruto)
                    
                    # 3. Fragmentação (Chunking)
                    pedacos = fragmentar_texto(conteudo_bruto)
                    
                    # 4. Vetorização (Salvando os pedaços separados, mas com a mesma etiqueta)
                    for idx, pedaco in enumerate(pedacos):
                        id_unico = f"{arquivo}_chunk_{idx}"
                        colecao.upsert(
                            documents=[pedaco], 
                            metadatas=[{"fonte": arquivo, "ano": ano, "setor": setor}], 
                            ids=[id_unico]
                        )
                        total_chunks += 1
                        
            st.success(f"✅ {len(arquivos)} arquivos processados em {total_chunks} fragmentos!")


# INTERFACE PRINCIPAL (BUSCA E RERANKING VIA IA)
st.title(" Pesquisa com Reranking de IA")
st.markdown("O sistema buscará os 10 fragmentos matematicamente mais próximos e a IA filtrará os mais relevantes (Foco no Setor e Data mais recente).")

pergunta = st.text_input("Sua dúvida:", placeholder="Ex: Qual nossa visão sobre Energia?")

if st.button("Gerar Análise", type="primary"):
    if pergunta:
        with st.spinner("Buscando vetores e aplicando Inteligência de Relevância..."):
            
            # PASSO 1: BUSCA VETORIAL (Trazemos 10 pedaços para dar opções para a IA)
            resultados = colecao.query(query_texts=[pergunta], n_results=10)
            
            textos_brutos = resultados['documents'][0]
            metadatas_brutos = resultados['metadatas'][0]
            
            contexto_para_ia = ""
            for texto, meta in zip(textos_brutos, metadatas_brutos):
                contexto_para_ia += f"\n[FONTE: {meta['fonte']} | SETOR: {meta['setor']} | ANO: {meta['ano']}]\n{texto}\n"

            # PASSO 2: RERANKING E GERAÇÃO VIA IA
            prompt_sistema = """
            Você é um motor de Inteligência Artificial especializado em Recuperação de Informação (RAG).
            Sua função é atuar como um Reranker e Analista.
            
            REGRAS DE RELEVÂNCIA OBRIGATÓRIAS:
            1. Leia a pergunta do usuário e identifique o setor desejado.
            2. Ignore os fragmentos que pertencem a setores diferentes da pergunta.
            3. Havendo documentos do mesmo setor, dê peso e destaque máximo àqueles com o 'ANO' mais recente.
            
            FORMATO DE RESPOSTA ESTRITO:
            LAUDO_DE_RELEVANCIA: [Explique em 1 linha quais arquivos você escolheu e o motivo (ex: priorizou ano X e setor Y)]
            FONTES_UTILIZADAS: [liste apenas os nomes dos arquivos usados, separados por vírgula]
            ---
            RESPOSTA:
            [Escreva a resposta de forma profissional, citando como a visão mais recente se sobrepõe às antigas]
            """

            try:
                resposta = cliente_llm.chat.completions.create(
                    messages=[
                        {"role": "system", "content": prompt_sistema},
                        {"role": "user", "content": f"FRAGMENTOS RECUPERADOS:\n{contexto_para_ia}\n\nPERGUNTA: {pergunta}"}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.1
                )
                
                resposta_completa = resposta.choices[0].message.content
                
                # PASSO 3: PARSING (Separando o laudo, as fontes e a resposta)
                try:
                    partes = resposta_completa.split("---")
                    cabecalhos = partes[0]
                    corpo_resposta = partes[1].replace("RESPOSTA:", "").strip()
                    
                    linhas_cabecalho = cabecalhos.split("\n")
                    laudo = ""
                    fontes_limpas = ""
                    for linha in linhas_cabecalho:
                        if "LAUDO_DE_RELEVANCIA:" in linha:
                            laudo = linha.replace("LAUDO_DE_RELEVANCIA:", "").strip()
                        elif "FONTES_UTILIZADAS:" in linha:
                            fontes_limpas = linha.replace("FONTES_UTILIZADAS:", "").replace("[", "").replace("]", "").strip()
                    
                    fontes_validas = [f.strip() for f in fontes_limpas.split(",") if f.strip()]
                except Exception as e:
                    corpo_resposta = resposta_completa
                    laudo = "Erro ao processar laudo."
                    fontes_validas = []

                # EXIBIÇÃO NA TELA
                st.subheader("💡 Resposta Final")
                st.info(corpo_resposta)
                
                st.write("---")
                # Mostramos o laudo da IA provando que ela pensou na relevância
                st.caption(f"🤖 **Justificativa da IA (Reranking):** {laudo}")
                
                st.subheader("📄 Fragmentos confirmados e utilizados:")
                
                # Só exibe os arquivos que a IA confirmou que passaram pelo filtro dela
                # Usamos um set() para não repetir o mesmo arquivo caso a IA tenha usado 2 chunks dele
                arquivos_exibidos = set()
                for meta in metadatas_brutos:
                    if meta['fonte'] in fontes_validas and meta['fonte'] not in arquivos_exibidos:
                        arquivos_exibidos.add(meta['fonte'])
                        st.success(f"**{meta['fonte']}** (Setor: {meta['setor']} | Ano: {meta['ano']})")
                
                if not arquivos_exibidos:
                    st.warning("A IA determinou que nenhum dos fragmentos recuperados era relevante para esta pergunta.")

            except Exception as e:
                st.error(f"Erro na geração da IA: {e}")