import streamlit as st
import googlemaps
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import json
import time
import requests
import numpy as np

# Configuração da página
st.set_page_config(
    page_title="🏢 Analisador de Terrenos Comerciais v2.0",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado para um design moderno (mantido o mesmo do original)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * {font-family: 'Inter', sans-serif;}
    .main {background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh;}
    .stApp > header {background-color: transparent;}
    .main-container {background: white; border-radius: 20px; margin: 20px; padding: 0; box-shadow: 0 20px 60px rgba(0,0,0,0.1); overflow: hidden;}
    .header-section {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 3rem 2rem; text-align: center; color: white;}
    .header-section h1 {font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;}
    .header-section p {font-size: 1.1rem; opacity: 0.9; font-weight: 300;}
    .content-section {padding: 2rem;}
    .input-group {background: #f8f9ff; border-radius: 15px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #e3e8ff;}
    .input-group h3 {color: #4c51bf; font-weight: 600; margin-bottom: 1rem; font-size: 1.3rem;}
    .tag-item {background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.85rem; margin: 0.2rem; display: inline-block; font-weight: 500;}
    .success-box {background: linear-gradient(135deg, #48bb78, #38a169); color: white; padding: 1rem; border-radius: 10px; margin: 1rem 0;}
    .error-box {background: linear-gradient(135deg, #f56565, #e53e3e); color: white; padding: 1rem; border-radius: 10px; margin: 1rem 0;}
    .metric-card {background: white; border-radius: 15px; padding: 1.5rem; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.05); border: 1px solid #e3e8ff;}
    .metric-value {font-size: 2rem; font-weight: 700; color: #4c51bf;}
    .metric-label {color: #6b7280; font-weight: 500; margin-top: 0.5rem;}
    .analysis-result {background: white; border-radius: 15px; padding: 2rem; margin: 1rem 0; box-shadow: 0 4px 20px rgba(0,0,0,0.05); border-left: 4px solid #667eea;}
    .recommendation-card {background: white; color: #333; border-radius: 15px; padding: 2rem; margin: 1rem 0; border: 1px solid #e3e8ff; box-shadow: 0 4px 20px rgba(0,0,0,0.05);}
    .stButton > button {background: linear-gradient(135deg, #667eea, #764ba2) !important; color: white !important; border: none !important; border-radius: 25px !important; font-weight: 600 !important; font-size: 1.1rem !important; padding: 0.75rem 2rem !important; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important; transition: all 0.3s ease !important;}
    .stButton > button:hover {transform: translateY(-2px) !important; box-shadow: 0 6px 25px rgba(102, 126, 234, 0.4) !important;}
    .sidebar .stSelectbox > div > div {background-color: #f8f9ff; border: 1px solid #e3e8ff; border-radius: 10px;}
    .footer {text-align: center; padding: 1.5rem; color: #a0aec0; font-size: 0.9rem;}
    pre {white-space: pre-wrap; word-wrap: break-word; background-color: #f8f9ff; padding: 1rem; border-radius: 10px; border: 1px solid #e3e8ff;}
</style>
""", unsafe_allow_html=True)

# Inicialização das variáveis de sessão
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = {}

# --- NOVAS FUNÇÕES E FUNÇÕES APRIMORADAS ---

@st.cache_data(ttl=3600)
def get_geocode(address, _gmaps_client):
    """Geocodifica um endereço e extrai informações adicionais como município e estado."""
    try:
        result = _gmaps_client.geocode(address)
        if result:
            data = {
                'lat': result[0]['geometry']['location']['lat'],
                'lon': result[0]['geometry']['location']['lng'],
                'formatted_address': result[0]['formatted_address'],
                'municipio': None,
                'estado_sigla': None
            }
            for comp in result[0]['address_components']:
                if 'administrative_area_level_2' in comp['types']:
                    data['municipio'] = comp['long_name']
                if 'administrative_area_level_1' in comp['types']:
                    data['estado_sigla'] = comp['short_name']
            return data
    except Exception as e:
        st.error(f"Erro ao geocodificar: {e}")
    return None

@st.cache_data(ttl=86400)
def get_municipio_ibge_code(nome_municipio, sigla_uf):
    """Obtém o código IBGE de 7 dígitos para um município."""
    try:
        url_estados = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
        estados = requests.get(url_estados).json()
        uf_id = next((e['id'] for e in estados if e['sigla'] == sigla_uf), None)
        if not uf_id:
            return None, "Estado não encontrado."

        url_municipios = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_id}/municipios"
        municipios = requests.get(url_municipios).json()
        municipio_info = next((m for m in municipios if m['nome'].lower() == nome_municipio.lower()), None)
        
        return (municipio_info['id'], None) if municipio_info else (None, "Município não encontrado na UF.")
    except Exception as e:
        return None, f"Erro ao buscar código do IBGE: {e}"

@st.cache_data(ttl=86400)
def get_dados_sidra(codigo_municipio):
    """Busca dados de Renda e PIB do IBGE Sidra para um município."""
    dados = {'renda': 'N/A', 'pib': 'N/A', 'renda_url': '', 'pib_url': ''}
    
    # Renda Média (PNAD Contínua - Tabela 6579)
    try:
        url_renda = f"https://apisidra.ibge.gov.br/values/t/6579/n6/{codigo_municipio}/v/9810/p/last/d/v9810%201"
        dados['renda_url'] = url_renda
        response = requests.get(url_renda).json()
        if len(response) > 1 and response[1].get('V') not in [None, '...']:
            valor = float(response[1]['V'])
            periodo = response[1]['P_NOME']
            dados['renda'] = f"R$ {valor:,.2f} (Rendimento médio per capita - {periodo})"
    except Exception:
        dados['renda'] = "Dado de renda indisponível no Sidra."

    # PIB per capita (Contas Regionais - Tabela 5938)
    try:
        url_pib = f"https://apisidra.ibge.gov.br/values/t/5938/n6/{codigo_municipio}/v/37/p/last"
        dados['pib_url'] = url_pib
        response = requests.get(url_pib).json()
        if len(response) > 1 and response[1].get('V') not in [None, '...']:
            valor = float(response[1]['V'])
            periodo = response[1]['P_NOME']
            dados['pib'] = f"R$ {valor:,.2f} (PIB per capita - {periodo})"
    except Exception:
        dados['pib'] = "Dado de PIB indisponível no Sidra."
        
    return dados

@st.cache_data(ttl=3600)
def get_detailed_nearby_places(lat, lon, radius, place_type, _gmaps_client, limit=20):
    """Busca por estabelecimentos próximos e obtém detalhes para cada um, com um limite."""
    analysis = {'count': 0, 'avg_rating': 0, 'details': [], 'error': None}
    try:
        # Etapa 1: Busca inicial (retorna até 20 locais)
        nearby_result = _gmaps_client.places_nearby(location=(lat, lon), radius=radius, type=place_type, language='pt-BR')
        places = nearby_result.get('results', [])
        analysis['count'] = len(places)

        detailed_places = []
        ratings = []
        
        # Etapa 2: Busca os detalhes apenas para os resultados até o limite definido.
        # Isso garante que o app não vai congelar.
        for place in places[:limit]: 
            place_id = place.get('place_id')
            if place_id:
                details = _gmaps_client.place(place_id, fields=['name', 'rating', 'user_ratings_total', 'price_level'])
                res = details.get('result', {})
                detailed_places.append({
                    'Nome': res.get('name', 'N/A'),
                    'Rating': res.get('rating', 0),
                    'Avaliações': res.get('user_ratings_total', 0),
                    'Nível de Preço': res.get('price_level', 0)
                })
                if 'rating' in res:
                    ratings.append(res['rating'])
        
        analysis['details'] = detailed_places
        if ratings:
            analysis['avg_rating'] = np.mean(ratings)

    except Exception as e:
        analysis['error'] = f"Erro ao buscar '{place_type}': {e}"
    return analysis
# --- INTERFACE DO USUÁRIO ---

st.markdown('<div class="main-container">', unsafe_allow_html=True)
st.markdown("""
    <div class="header-section">
        <h1>🏢 Analisador de Terrenos Comerciais v2.0</h1>
        <p>Análise inteligente de potencial comercial com dados atualizados e IA</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar para configurações de API
with st.sidebar:
    st.markdown("### ⚙️ Configurações de API")
    with st.expander("🗺️ Google Maps API", expanded=True):
        gmaps_api_key = st.text_input("API Key do Google Maps", type="password")
        gmaps = googlemaps.Client(key=gmaps_api_key) if gmaps_api_key else None
        if gmaps: st.success("✅ Google Maps conectado")
        else: st.warning("⚠️ API Key necessária")

    with st.expander("🤖 Gemini AI API", expanded=True):
        gemini_api_key = st.text_input("API Key do Gemini", type="password")
        model = None
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel('gemini-1.5-pro')
                st.success("✅ Gemini AI conectado")
            except Exception as e:
                st.error(f"❌ Erro: {e}")
        else:
            st.warning("⚠️ API Key necessária")

    st.markdown("---")
    st.markdown("### 🛠️ Ferramentas")
    debug_mode = st.toggle("Ativar modo Debug", value=False, help="Exibe os dados brutos coletados em cada etapa da análise.")
    
    st.markdown("---")
    st.markdown("### 📊 Status da Análise")
    if st.session_state.analysis_complete:
        st.success("✅ Análise concluída")
        if st.button("🔄 Nova Análise"):
            st.session_state.analysis_complete = False
            st.session_state.analysis_data = {}
            st.rerun()
    else:
        st.info("⏳ Aguardando dados")

# Conteúdo principal
st.markdown('<div class="content-section">', unsafe_allow_html=True)

# Inputs do usuário
col1, col2 = st.columns([1, 1])
with col1:
    st.markdown('<div class="input-group"><h3>📍 Localização do Terreno</h3></div>', unsafe_allow_html=True)
    address_input = st.text_input("Endereço Completo", placeholder="Ex: Avenida Paulista, 1578, São Paulo, SP", key="address")
    col1a, col1b = st.columns(2)
    radius_input = col1a.selectbox("Raio de Análise", options=[300, 500, 700, 1000, 1500, 2000], index=2, format_func=lambda x: f"{x}m")
    area_terreno = col1b.number_input("Área do Terreno (m²)", min_value=10, max_value=50000, value=200, step=50)

with col2:
    st.markdown('<div class="input-group"><h3>🏪 Tipos de Estabelecimentos</h3></div>', unsafe_allow_html=True)
    tipos_disponiveis = {'restaurant': '🍽️ Restaurantes', 'cafe': '☕ Cafeterias', 'pharmacy': '💊 Farmácias', 'convenience_store': '🏪 Conveniências', 'gym': '💪 Academias', 'bank': '🏧 Bancos', 'clothing_store': '👕 Lojas de Roupa', 'supermarket': '🛒 Supermercados', 'gas_station': '⛽ Postos', 'beauty_salon': '💅 Salões', 'bakery': '🥖 Padarias', 'book_store': '📚 Livrarias'}
    tipos_selecionados = st.multiselect("Selecione os tipos para análise", options=list(tipos_disponiveis.keys()), default=['restaurant', 'cafe', 'pharmacy', 'supermarket'], format_func=lambda x: tipos_disponiveis[x])
    tipos_customizados = st.text_area("Tipos adicionais (um por linha)", placeholder="hospital\nschool\npet_store", height=100)
    
    novos_tipos_display = []
    if tipos_customizados:
        # Pega os nomes amigáveis para exibir como tags
        novos_tipos_display = [tipo.strip() for tipo in tipos_customizados.split('\n') if tipo.strip()]
        # Cria os nomes para a API e os adiciona à lista de análise
        novos_tipos = [tipo.lower().replace(" ", "_") for tipo in novos_tipos_display]
        tipos_selecionados.extend(novos_tipos)


st.markdown("""
<div class="input-group">
    <h3>📝 Informações Contextuais</h3>
</div>
""", unsafe_allow_html=True)
tags_categorias = {
    "🚦 Tráfego": ["Alto fluxo de pedestres", "Trânsito intenso de veículos", "Área residencial calma", "Rua comercial movimentada", "Via de acesso principal"],
    "👥 Público-Alvo": ["Executivos e profissionais", "Famílias com crianças", "Jovens e universitários", "Turistas frequentes", "Idosos e aposentados", "Classe média alta", "Trabalhadores locais"],
    "🏙️ Características": ["Próximo ao transporte público", "Área nobre da cidade", "Centro comercial", "Bairro em crescimento", "Região empresarial", "Zona residencial", "Área turística"],
    "⏰ Período de Movimento": ["Movimentado durante a semana", "Maior movimento nos finais de semana", "Vida noturna ativa", "Horário comercial tradicional", "24 horas por dia"]
}
col_tags1, col_tags2 = st.columns([1, 1])
with col_tags1:
    st.markdown("**🏷️ Tags Rápidas**")
    tags_selecionadas = []
    for categoria, opcoes in tags_categorias.items():
        with st.expander(categoria):
            for opcao in opcoes:
                if st.checkbox(opcao, key=f"tag_{opcao}"):
                    tags_selecionadas.append(opcao)
with col_tags2:
    st.markdown("**✍️ Observações Personalizadas**")
    manual_input = st.text_area("", placeholder="Descreva características específicas da região, comportamento do público, eventos sazonais, concorrência conhecida, etc.", height=200)

# Combina as tags dos checkboxes, os tipos customizados e as observações para exibição
all_tags_to_display = tags_selecionadas + novos_tipos_display
if manual_input:
    all_tags_to_display.append(manual_input)

if all_tags_to_display:
    st.markdown("**Tags, Tipos e Observações Selecionadas:**")
    st.markdown("".join([f'<span class="tag-item">{tag}</span>' for tag in all_tags_to_display]), unsafe_allow_html=True)

info_completa = (" | ".join(tags_selecionadas) + " | " + manual_input) if tags_selecionadas and manual_input else (" | ".join(tags_selecionadas) if tags_selecionadas else manual_input)

# Botão de análise
st.markdown("### ")
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn2:
    analyze_button = st.button("🚀 Iniciar Análise Completa", type="primary", use_container_width=True)

# --- LÓGICA DA ANÁLISE ---
if analyze_button:
    # Validações iniciais
    if not all([address_input, gmaps, model, tipos_selecionados]):
        if not address_input: st.markdown('<div class="error-box">❌ Por favor, insira o endereço do terreno</div>', unsafe_allow_html=True)
        if not gmaps: st.markdown('<div class="error-box">❌ Configure a API do Google Maps</div>', unsafe_allow_html=True)
        if not model: st.markdown('<div class="error-box">❌ Configure a API do Gemini</div>', unsafe_allow_html=True)
        if not tipos_selecionados: st.markdown('<div class="error-box">❌ Selecione pelo menos um tipo de estabelecimento</div>', unsafe_allow_html=True)
    else:
        # Containers para progresso e debug
        progress_container = st.container()
        debug_container = st.expander("🔍 Painel de Debug", expanded=True) if debug_mode else st.empty()

        with progress_container:
            progress_bar = st.progress(0, text="Iniciando análise...")
        
        analysis_data = {}

        # Etapa 1: Geocodificação
        progress_bar.progress(5, text="🗺️ Geocodificando endereço...")
        geocode_data = get_geocode(address_input, gmaps)
        
        with debug_container:
            st.markdown("--- \n**DEBUG: Etapa 1 - Geocodificação**")
            st.json(geocode_data if geocode_data else {"error": "Endereço não encontrado."})

        if not geocode_data:
            st.markdown('<div class="error-box">❌ Endereço não encontrado. Verifique e tente novamente.</div>', unsafe_allow_html=True)
        else:
            analysis_data.update(geocode_data)
            
            # Etapa 2: Obter código do IBGE
            progress_bar.progress(15, text="🏦 Buscando código do município no IBGE...")
            ibge_code, error_msg = get_municipio_ibge_code(geocode_data['municipio'], geocode_data['estado_sigla'])
            analysis_data['ibge_code'] = ibge_code

            with debug_container:
                st.markdown("--- \n**DEBUG: Etapa 2 - Código IBGE**")
                st.write(f"Município: {geocode_data['municipio']} - {geocode_data['estado_sigla']}")
                st.write(f"Código IBGE encontrado: {ibge_code if ibge_code else error_msg}")

            # Etapa 3: Dados Socioeconômicos (Sidra)
            dados_sidra = {}
            if ibge_code:
                progress_bar.progress(25, text="📈 Coletando dados socioeconômicos (IBGE Sidra)...")
                dados_sidra = get_dados_sidra(ibge_code)
                analysis_data['dados_sidra'] = dados_sidra
            
            with debug_container:
                st.markdown("--- \n**DEBUG: Etapa 3 - Dados Socioeconômicos (Sidra)**")
                st.write(f"URL da Renda: `{dados_sidra.get('renda_url', 'N/A')}`")
                st.write(f"URL do PIB: `{dados_sidra.get('pib_url', 'N/A')}`")
                st.json(dados_sidra)

            # Etapa 4: Análise detalhada de estabelecimentos
            progress_bar.progress(40, text="🏪 Analisando concorrência detalhadamente...")
            comercio_detalhado = {}
            total_tipos = len(tipos_selecionados)
            for i, tipo in enumerate(tipos_selecionados):
                progress_bar.progress(40 + int(40 * (i + 1) / total_tipos), text=f"Analisando: {tipos_disponiveis.get(tipo, tipo)}")
                comercio_detalhado[tipo] = get_detailed_nearby_places(geocode_data['lat'], geocode_data['lon'], radius_input, tipo, gmaps)
            
            analysis_data['comercio_detalhado'] = comercio_detalhado
            with debug_container:
                st.markdown("--- \n**DEBUG: Etapa 4 - Análise de Concorrência**")
                st.json(comercio_detalhado)

            # Etapa 5: Geração de recomendação com IA
            progress_bar.progress(85, text="🤖 Gerando recomendação com IA...")
            
            # Construir prompt para o Gemini
            prompt_concorrencia = ""
            for tipo, dados in comercio_detalhado.items():
                nome_tipo = tipos_disponiveis.get(tipo, tipo.replace('_', ' ').title())
                prompt_concorrencia += f"\n   • **{nome_tipo}:** {dados['count']} estabelecimentos. Rating médio: {dados['avg_rating']:.2f}."

            prompt = f"""
            Você é um assistente especialista em geomarketing e análise de terrenos para empreendimentos comerciais no Brasil.
            Analise os dados fornecidos e gere uma recomendação detalhada, estruturada e acionável.

            **DADOS PARA ANÁLISE:**
            1. **Localização:** {geocode_data['formatted_address']}
            2. **Área do terreno:** {area_terreno}m²
            3. **Raio da análise:** {radius_input} metros
            4. **Dados Socioeconômicos do Município ({geocode_data['municipio']}):**
               - Renda: {dados_sidra.get('renda', 'Não disponível')}
               - PIB: {dados_sidra.get('pib', 'Não disponível')}
            5. **Análise de Concorrência (quantitativa e qualitativa no raio):**
               {prompt_concorrencia}
            6. **Informações Contextuais (fornecidas pelo usuário):**
               {info_completa if info_completa else 'Nenhuma.'}

            **INSTRUÇÕES:**
            Forneça uma análise estruturada em markdown com os seguintes tópicos:
            
            ## 🎯 Resumo Executivo
            Uma síntese do potencial comercial da área, considerando todos os dados. Dê um parecer geral: alto, médio ou baixo potencial e por quê.
            
            ## 📊 Análise do Ecossistema Local
            Interprete os dados. O que a renda e o PIB dizem sobre o poder de compra local? Como a concorrência se apresenta? Existem saturações ou lacunas de mercado evidentes (ex: muitos restaurantes de nota baixa = oportunidade para um de alta qualidade)?
            
            ## 💡 Top 3 Recomendações de Negócio
            Sugira os 3 melhores tipos de negócio, ordenados por potencial. Para cada um, forneça:
            - **Tipo de Negócio:** (Ex: Cafeteria de Especialidade)
            - **Justificativa:** Explique por que é uma boa escolha, conectando com os dados de renda, concorrência (quantidade e qualidade), e contexto do usuário.
            - **Público-Alvo:** Descreva o perfil do cliente ideal.
            - **Considerações Estratégicas:** Dicas sobre como se diferenciar da concorrência local.
            
            ## ⚠️ Riscos e Pontos de Atenção
            Para cada recomendação, aponte os principais desafios (ex: concorrência forte, necessidade de alto investimento inicial, etc.).
            
            ## ❗ Aviso Legal
            Inclua uma nota sobre a necessidade de verificar o zoneamento local e as leis municipais.

            Seja específico, use os dados fornecidos e mantenha o foco em viabilidade comercial real.
            """

            with debug_container:
                st.markdown("--- \n**DEBUG: Etapa 5 - Prompt enviado para a IA**")
                st.text(prompt)

            try:
                response = model.generate_content(prompt)
                recomendacao_ia = response.text
                
                progress_bar.progress(100, "✅ Análise concluída!")
                time.sleep(1)
                
                st.session_state.analysis_data = {**analysis_data, 'address': address_input, 'radius': radius_input, 'area': area_terreno, 'tipos_disponiveis': tipos_disponiveis, 'info_completa': info_completa, 'recomendacao': recomendacao_ia, 'timestamp': datetime.now()}
                st.session_state.analysis_complete = True
                progress_container.empty()
                
            except Exception as e:
                st.markdown(f'<div class="error-box">❌ Erro ao gerar recomendação: {e}</div>', unsafe_allow_html=True)
                progress_bar.empty()
        
        st.rerun() # Reroda o script para exibir os resultados

# --- EXIBIÇÃO DOS RESULTADOS ---
if st.session_state.analysis_complete and st.session_state.analysis_data:
    data = st.session_state.analysis_data
    
    st.markdown("--- \n## 📊 Resultados da Análise")
    
    col_mapa, col_visao = st.columns([2,1])
    with col_mapa:
        st.markdown("### 🗺️ Localização e Área de Análise")
        m = folium.Map(location=[data['lat'], data['lon']], zoom_start=16)
        folium.Marker([data['lat'], data['lon']], popup=f"<strong>{data['address']}</strong><br>Área: {data['area']}m²", tooltip="Local do Terreno", icon=folium.Icon(color='red', icon='building', prefix='fa')).add_to(m)
        folium.Circle([data['lat'], data['lon']], radius=data['radius'], color='#667eea', fill=True, fill_color='#667eea', fill_opacity=0.2, popup=f"Raio de análise: {data['radius']}m").add_to(m)
        st_folium(m, width=700, height=350)

    with col_visao:
        st.markdown("### 👁️ Visão da Rua")
        if gmaps_api_key:
            st.image(f"https://maps.googleapis.com/maps/api/streetview?size=600x400&location={data['lat']},{data['lon']}&key={gmaps_api_key}", caption="Visão a partir do endereço fornecido")
        else:
            st.warning("API Key do Google Maps necessária para exibir o Street View.")

    # Dados socioeconômicos
    if data.get('dados_sidra'):
        st.markdown("### 📈 Análise Socioeconômica")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{data['dados_sidra'].get('renda', 'N/A')}</div>
                <div class="metric-label">Renda Média</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{data['dados_sidra'].get('pib', 'N/A')}</div>
                <div class="metric-label">PIB per Capita</div>
            </div>""", unsafe_allow_html=True)
        st.caption(f"Fonte: IBGE Sidra para o município de {data['municipio']}")
    
    # Análise de concorrência
    st.markdown("### 🏪 Análise de Concorrência")
    
    df_comercio = pd.DataFrame([
        {'Tipo': data['tipos_disponiveis'].get(tipo, tipo.replace('_', ' ').title()), 'Quantidade': dados['count']} 
        for tipo, dados in data['comercio_detalhado'].items()
    ])
    
    tab1, tab2 = st.tabs(["Visão Geral", "Análise Detalhada"])

    with tab1:
        fig = px.bar(df_comercio.sort_values('Quantidade', ascending=True), x='Quantidade', y='Tipo', orientation='h', title=f"Estabelecimentos no raio de {data['radius']}m", color='Quantidade', color_continuous_scale='viridis', text='Quantidade')
        fig.update_layout(height=400, showlegend=False, yaxis_title=None, xaxis_title="Quantidade")
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        for tipo, dados in data['comercio_detalhado'].items():
            nome_tipo = data['tipos_disponiveis'].get(tipo, tipo.replace('_', ' ').title())
            if dados['details']:
                with st.expander(f"**{nome_tipo}** - {dados['count']} encontrados | Rating médio: {dados['avg_rating']:.2f}"):
                    df_details = pd.DataFrame(dados['details'])
                    df_details['Nível de Preço'] = df_details['Nível de Preço'].apply(lambda x: '💲' * x if x > 0 else 'N/A')
                    st.dataframe(df_details, use_container_width=True)
            else:
                 st.info(f"Nenhum estabelecimento do tipo '{nome_tipo}' encontrado ou sem detalhes disponíveis.")
    
    # Recomendação da IA
    st.markdown("### 🤖 Recomendação Inteligente da IA")
    st.markdown(f'<div class="recommendation-card">{data["recomendacao"]}</div>', unsafe_allow_html=True)
    
    # Download do relatório
    st.markdown("### 📄 Relatório Completo")
    
    # ... (código do relatório atualizado) ...
    relatorio_texto = f"""
RELATÓRIO DE ANÁLISE DE TERRENO COMERCIAL
==========================================
Data da análise: {data['timestamp'].strftime('%d/%m/%Y às %H:%M')}

INFORMAÇÕES DO TERRENO:
- Endereço: {data['address']}
- Município: {data['municipio']}
- Área do terreno: {data['area']}m²
- Raio de análise: {data['radius']}m

DADOS SOCIOECONÔMICOS (IBGE SIDRA):
- Renda Média: {data.get('dados_sidra', {}).get('renda', 'N/A')}
- PIB per Capita: {data.get('dados_sidra', {}).get('pib', 'N/A')}

INFORMAÇÕES CONTEXTUAIS FORNECIDAS:
{data['info_completa'] if data['info_completa'] else 'Nenhuma.'}

ANÁLISE DE CONCORRÊNCIA:
"""
    for tipo, dados in data['comercio_detalhado'].items():
        relatorio_texto += f"\n- {data['tipos_disponiveis'].get(tipo, tipo)}: {dados['count']} locais, rating médio de {dados['avg_rating']:.2f}"

    relatorio_texto += f"\n\nRECOMENDAÇÃO DA IA:\n{'='*20}\n{data['recomendacao']}"
    
    st.download_button(
        label="📝 Baixar Relatório TXT",
        data=relatorio_texto.encode('utf-8'),
        file_name=f"relatorio_terreno_{data['timestamp'].strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain"
    )

# Seção final e fechamento das tags
st.markdown("</div>", unsafe_allow_html=True) # Fecha a content-section
st.markdown('<div class="footer"><p>Desenvolvido como uma ferramenta de análise de geomarketing v2.0.</p></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True) # Fecha a main-container