
import matplotlib
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from bcb import PTAX
import os

# ==============================
# Função para baixar planilha do GitHub
def baixar_planilha_github(url, caminho_destino):
    try:
        resposta = requests.get(url)
        if resposta.status_code == 200:
            with open(caminho_destino, 'wb') as f:
                f.write(resposta.content)
            st.success(f"Planilha baixada com sucesso de {url}")
            return True
        else:
            st.error(f"Falha ao baixar planilha: {resposta.status_code}")
            return False
    except Exception as e:
        st.error(f"Erro ao baixar planilha: {e}")
        return False
# Configurações
# ==============================
TICKERS = {
    "cme": "6L=F", "brl_usd": "BRLUSD=X", 
    "xauusd": "GC=F", "dxy": "DX-Y.NYB"
}
URLS = {"gold_price_brl": "https://www.melhorcambio.com/ouro-hoje"}
HEADERS = {'User-Agent': 'Mozilla/5.0'}
DEFAULT_EXCEL_PATH = r"C:\Users\user\Documents\planilhas\ddeprofit.xlsx"

# ==============================
# Funções Utilitárias
# ==============================
def safe_execute(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        st.error(f"Erro ao executar {func.__name__}: {e}")
        return None

def extrair_valor(df, ativo, coluna):
    try:
        return float(df.loc[df['Asset'] == ativo, coluna].values[0])
    except:
        return None

def calcular_vencimento_wdo(data_base):
    mes = data_base.month + 1 if data_base.month < 12 else 1
    ano = data_base.year if data_base.month < 12 else data_base.year + 1
    primeiro_dia = datetime(ano, mes, 1)
    
    while primeiro_dia.weekday() >= 5:
        primeiro_dia += timedelta(days=1)
    return primeiro_dia

# ==============================
# Funções de Dados
# ==============================
def obter_cotacoes_yfinance(ticker, period="5d"):
    try:
        data = yf.Ticker(ticker).history(period=period)
        if data.empty:
            return None
        return {
            'open': data['Open'].iloc[-1],
            'high': data['High'].iloc[-1], 
            'low': data['Low'].iloc[-1],
            'close': data['Close'].iloc[-1]
        }
    except Exception as e:
        st.error(f"Erro ao obter dados para {ticker}: {e}")
        return None

def obter_valor_grama_ouro_reais():
    try:
        response = requests.get(URLS["gold_price_brl"], headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        valor = soup.find('input', {'id': 'comercial'}).get('value')
        return float(valor.replace(',', '.'))
    except Exception as e:
        st.error(f"Erro ao obter valor do ouro: {e}")
        return None

def obter_variacao_dxy():
    cotacoes = obter_cotacoes_yfinance(TICKERS["dxy"])
    if not cotacoes:
        return None
    try:
        historico = yf.Ticker(TICKERS["dxy"]).history(period="5d")
        if len(historico) >= 2:
            anterior = historico['Close'].iloc[-2]
            atual = historico['Close'].iloc[-1]
            return round(((atual - anterior) / anterior) * 100, 2)
    except:
        return None

def carregar_dados_excel():
    try:
        # URL do arquivo ddeprofit.xlsx no GitHub
        url_github = "https://raw.githubusercontent.com/Mvrsant/calculoswdo/main/ddeprofit.xlsx"
        caminho_local = "ddeprofit.xlsx"
        # Baixa o arquivo se não existir localmente
        if not os.path.exists(caminho_local):
            baixar_planilha_github(url_github, caminho_local)
        data = pd.read_excel(caminho_local)
        st.success(f"Planilha carregada: {caminho_local}")

        # Valida colunas
        required_columns = ['Asset', 'Fechamento Anterior', 'Último']
        if not all(col in data.columns for col in required_columns):
            st.warning("⚠️ Colunas ausentes no arquivo Excel")
            return None

        data['Asset'] = data['Asset'].str.strip()
        # Extrai dados
        current_date = datetime.today()
        expiration_date = calcular_vencimento_wdo(current_date)
        business_days = len(pd.bdate_range(start=current_date, end=expiration_date))

        return {
            "wdo_fut": extrair_valor(data, 'WDOFUT', 'Fechamento Anterior'),
            "dolar_spot": extrair_valor(data, 'USD/BRL', 'Fechamento Anterior'),
            "di1_fut": extrair_valor(data, 'DI1FUT', 'Último'),
            "frp0": extrair_valor(data, 'FRP0', 'Último'),
            "expiration_date": expiration_date.strftime('%d/%m/%Y'),
            "business_days_remaining": business_days
        }
    except Exception as e:
        st.error(f"Erro ao carregar Excel: {e}")
        return None

def extrair_sup_vol_b3():
    try:
        # URL do arquivo ddeprofit.xlsx no GitHub
        url_github = "https://raw.githubusercontent.com/Mvrsant/calculoswdo/main/ddeprofit.xlsx"
        caminho_local = "ddeprofit.xlsx"
        # Baixa o arquivo se não existir localmente
        if not os.path.exists(caminho_local):
            baixar_planilha_github(url_github, caminho_local)
        df_b3 = pd.read_excel(caminho_local, sheet_name="base_b3", header=None)
        return float(df_b3.iloc[18, 6])
    except Exception as e:
        st.error(f"Erro ao extrair SUP_VOLB3: {e}")
        return None

def obter_cotacoes_ptax():
    try:
        ptax = PTAX()
        endpoint = ptax.get_endpoint('CotacaoMoedaPeriodo')
        data_consulta = datetime.today().date()
        
        while True:
            data_str = data_consulta.strftime('%m.%d.%Y')
            df = (endpoint.query()
                  .parameters(moeda='USD', dataInicial=data_str, dataFinalCotacao=data_str)
                  .collect())
            if not df.empty:
                break
            data_consulta -= timedelta(days=1)
            
        df['dataHoraCotacao'] = pd.to_datetime(df['dataHoraCotacao'])
        df_dia = df[df['dataHoraCotacao'].dt.date == data_consulta]
        df_dia = df_dia.sort_values(by='dataHoraCotacao').reset_index(drop=True)
        
        # Captura data e hora das cotações
        cotacoes = []
        for idx, row in df_dia.iterrows():
            cotacoes.append({
                'valor': row['cotacaoVenda'],
                'data': row['dataHoraCotacao'].strftime('%d/%m/%Y'),
                'hora': row['dataHoraCotacao'].strftime('%H:%M:%S')
            })
        # Preenche até 4 cotações
        while len(cotacoes) < 4:
            cotacoes.append(None)
        return cotacoes[:4]
    except Exception as e:
        st.error(f"Erro ao obter cotações PTAX: {e}")
        return [None] * 4

# ==============================
# Funções de Cálculo
# ==============================
def calcular_paridade_ouro(xauusd, valor_grama_ouro_reais):
    if None in (xauusd, valor_grama_ouro_reais):
        return None
    return round((valor_grama_ouro_reais / (xauusd / 31.1035)) * 1000, 4)

def calcular_abertura_wdo(wdo_fechamento, dxy_variacao):
    if None in (wdo_fechamento, dxy_variacao):
        return None
    return round(wdo_fechamento * (1 + dxy_variacao / 100), 4)

def calcular_over(di1_fut, business_days):
    if None in (di1_fut, business_days):
        return None
    return round(((1 + di1_fut)**(1/252) - 1) * business_days, 5)

def calcular_preco_justo(dolar_spot, over):
    if None in (dolar_spot, over):
        return None
    return round(dolar_spot * (1 + over / 100), 4)

def calcular_bandas(wdo_abertura, over, sup_volb3, multiplicador=1.0):
    if None in (wdo_abertura, over, sup_volb3):
        return None
    
    deslocamento = (wdo_abertura * over / 100) + sup_volb3
    if multiplicador == 1.0:  # Bandas normais
        return {
            "1ª Máxima": round(wdo_abertura + deslocamento, 2),
            "1ª Mínima": round(wdo_abertura - deslocamento, 2),
            "2ª Máxima": round((wdo_abertura + deslocamento) * 1.005, 2),
            "2ª Mínima": round((wdo_abertura - deslocamento) * 0.995, 2)
        }
    else:  # Para PTAX
        return deslocamento

def calcular_bandas_ptax(wdo_abertura, over, sup_volb3, ptaxes):
    deslocamento = calcular_bandas(wdo_abertura, over, sup_volb3, 0)
    if deslocamento is None:
        return None
        
    resultado = {
        "Deslocamento PTAX (valor)": round(deslocamento, 5),
        "Deslocamento PTAX (pontos)": round(deslocamento * 1000, 4)
    }
    
    for i, ptax in enumerate(ptaxes, 1):
        if ptax is None:
            continue
        base = ptax['valor'] * 1000
        resultado.update({
            f"1ª Máxima PTAX{i}": round(base + deslocamento, 2),
            f"1ª Mínima PTAX{i}": round(base - deslocamento, 2),
            f"2ª Máxima PTAX{i}": round((base + deslocamento) * 1.005, 2),
            f"2ª Mínima PTAX{i}": round((base - deslocamento) * 0.995, 2),
            f"Data PTAX{i}": ptax['data'],
            f"Hora PTAX{i}": ptax['hora']
        })
    return resultado
def criar_tabela_bandas_ptax(bandas_ptax, qtde_ptax):
    """Cria uma tabela organizada das bandas PTAX"""
    if not bandas_ptax or qtde_ptax == 0:
        return None
    
    # Criar estrutura da tabela
    dados_tabela = {
        "Tipo de Banda": ["1ª Máxima", "1ª Mínima", "2ª Máxima", "2ª Mínima"],
        "Data": [bandas_ptax.get(f'Data PTAX{i}', '-') for i in range(1, qtde_ptax + 1)],
        "Hora": [bandas_ptax.get(f'Hora PTAX{i}', '-') for i in range(1, qtde_ptax + 1)]
    }
    # Adicionar colunas para cada PTAX disponível
    for i in range(1, qtde_ptax + 1):
        coluna_nome = f"PTAX {i}"
        dados_tabela[coluna_nome] = [
            bandas_ptax.get(f'1ª Máxima PTAX{i}', '-'),
            bandas_ptax.get(f'1ª Mínima PTAX{i}', '-'),
            bandas_ptax.get(f'2ª Máxima PTAX{i}', '-'),
            bandas_ptax.get(f'2ª Mínima PTAX{i}', '-')
        ]
    return pd.DataFrame(dados_tabela)

def exibir_metricas_ptax(ptax_validas):
    """Exibe as cotações PTAX em formato de métricas organizadas"""
    if not ptax_validas:
        return
        
    qtde = len(ptax_validas)
    
    # Organizar em até 4 colunas
    if qtde <= 2:
        cols = st.columns(qtde)
    elif qtde == 3:
        cols = st.columns(3)
    else:
        cols = st.columns(4)
    
    for i, ptax in enumerate(ptax_validas):
        if ptax is None:
            continue
        with cols[i % len(cols)]:
            st.metric(
                label=f"🏦 PTAX {i+1}", 
                value=f"R$ {ptax['valor']:.4f}",
                help=f"Cotação PTAX número {i+1} do dia\nData: {ptax['data']}\nHora: {ptax['hora']}"
            )

# ==============================
# Interface Principal
# ==============================
def criar_dataframe_cotacoes(cotacoes, nome):
    if not cotacoes:
        return None
    data = {
        "Métrica": ["Abertura", "Fechamento", "Máxima", "Mínima"],
        f"Cotação ({nome})": [cotacoes['open'], cotacoes['close'], cotacoes['high'], cotacoes['low']]
    }
    df = pd.DataFrame(data)
    df["Valor Calculado"] = (1 / df[f"Cotação ({nome})"] * 1000).round(2)
    return df

def main():
    st.title("📈 Cálculos WDO - Mini Contrato Futuro de Dólar")
    
    # Carregamento de dados
    with st.spinner("Carregando dados..."):
        dados_excel = safe_execute(carregar_dados_excel)
        sup_volb3 = safe_execute(extrair_sup_vol_b3)
        
        # Cotações
        xauusd_data = obter_cotacoes_yfinance(TICKERS["xauusd"])
        xauusd = xauusd_data['close'] if xauusd_data else None
        
        valor_ouro_brl = safe_execute(obter_valor_grama_ouro_reais)
        dxy_variacao = safe_execute(obter_variacao_dxy)
        ptax_cotacoes = safe_execute(obter_cotacoes_ptax)

    # Cálculos principais
    wdo_abertura = over = preco_justo = None
    if dados_excel:
        wdo_abertura = calcular_abertura_wdo(dados_excel.get("wdo_fut"), dxy_variacao)
        over = calcular_over(dados_excel.get("di1_fut"), dados_excel.get("business_days_remaining"))
        preco_justo = calcular_preco_justo(dados_excel.get("dolar_spot"), over)

    # Abas
    tab1, tab2, tab3, tab4 = st.tabs([
        "📉 Paridades CME/BRLUSD", "📊 Dados Carregados", 
        "📈 Abertura Calculada", "🧾 Cotações PTAX"
    ])

    with tab1:
        # Definir cores para cada paridade
        cores = {
            "CME - 6L": "background-color: #e0f7fa; color: #006064;",
            "BRL/USD": "background-color: #fff3e0; color: #e65100;"
        }
        for ticker_key, nome in [("cme", "CME - 6L"), ("brl_usd", "BRL/USD")]:
            cotacoes = obter_cotacoes_yfinance(TICKERS[ticker_key])
            df = criar_dataframe_cotacoes(cotacoes, nome)
            if df is not None:
                st.write(f"### {nome}")
                # Aplica cor na coluna da cotação
                def highlight_col(s):
                    return [cores[nome] if col == f"Cotação ({nome})" else "" for col in s.index]
                styled_df = df.style.apply(highlight_col, axis=1)
                # Aplica gradiente na coluna Valor Calculado para facilitar visualização
                styled_df = styled_df.background_gradient(subset=["Valor Calculado"], cmap="YlGn")
                st.dataframe(styled_df, use_container_width=True)

    with tab2:
        st.subheader("📄 Dados Carregados")
        if dados_excel:
            st.dataframe(dados_excel)
        else:
            st.warning("Não foi possível carregar os dados do Excel.")

    with tab3:
        # Paridade Ouro e principais métricas em tabela
        paridade_ouro = calcular_paridade_ouro(xauusd, valor_ouro_brl)
        dados_tabela = {
            "Métrica": [
                "Ouro Spot", "Ouro R$", "Paridade Ouro", "Abertura WDO", "Over (DI1)", "Preço Justo"
            ],
            "Valor": [
                f"{xauusd:.2f}" if xauusd else "N/A",
                f"{valor_ouro_brl:.2f}" if valor_ouro_brl else "N/A",
                f"{paridade_ouro:.4f}" if paridade_ouro else "N/A",
                f"{wdo_abertura:.4f}" if wdo_abertura is not None else "N/A",
                f"{over:.4f}" if over is not None else "N/A",
                f"{preco_justo:.4f}" if preco_justo is not None else "N/A"
            ]
        }
        df_metricas = pd.DataFrame(dados_tabela)
        # Aplica gradiente para facilitar visualização
        styled_df = df_metricas.style.applymap(
            lambda v: "background-color: #e3f2fd; color: #0d47a1;" if "N/A" not in v else "background-color: #ffcdd2; color: #b71c1c;",
            subset=["Valor"]
        )
        st.write("### ⚖️ Paridade Ouro e Métricas Calculadas")
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Bandas
        if all(x is not None for x in [wdo_abertura, over, sup_volb3]):
            bandas = calcular_bandas(wdo_abertura, over, sup_volb3)
            bandas_tabela = {
                "Banda": ["1ª Máxima", "2ª Máxima", "1ª Mínima", "2ª Mínima"],
                "Valor": [
                    bandas["1ª Máxima"],
                    bandas["2ª Máxima"],
                    bandas["1ª Mínima"],
                    bandas["2ª Mínima"]
                ]
            }
            df_bandas = pd.DataFrame(bandas_tabela)
            styled_bandas = df_bandas.style.background_gradient(subset=["Valor"], cmap="YlOrRd")
            st.write("### 📊 Bandas de Máximas e Mínimas")
            st.metric("VOL B3", sup_volb3)
            st.dataframe(styled_bandas, use_container_width=True, hide_index=True)

    with tab4:
        ptax_validas = [p for p in ptax_cotacoes if p is not None]
        qtde = len(ptax_validas)
        
        # Header com informações gerais
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🧾 Cotações PTAX do Dia")
        with col2:
            st.metric(
                label="📊 Disponibilidade", 
                value=f"{qtde}/4",
                delta=f"{qtde*25}% completo"
            )
        
        # Barra de progresso
        progress_bar = st.progress(qtde / 4)
        if qtde < 4:
            st.info("⏳ Aguardando próximas cotações da PTAX...")
        else:
            st.success("✅ Todas as cotações PTAX do dia estão disponíveis!")
            
        # Exibir cotações PTAX de forma organizada
        if qtde > 0:
            st.write("### 💰 Cotações Atuais")
            exibir_metricas_ptax(ptax_validas)
            
            # Separador visual
            st.divider()
            
            # Calcular e exibir informações do deslocamento
            bandas_ptax = calcular_bandas_ptax(wdo_abertura, over, sup_volb3, ptax_cotacoes)
            
            if bandas_ptax:
                # Informações do deslocamento
                st.write("### 📐 Parâmetros de Cálculo")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric(
                        "🎯 Deslocamento (Valor)", 
                        f"{bandas_ptax['Deslocamento PTAX (valor)']:.5f}",
                        help="Deslocamento base usado no cálculo das bandas"
                    )
                
                with col2:
                    st.metric(
                        "📍 Deslocamento (Pontos)", 
                        f"{bandas_ptax['Deslocamento PTAX (pontos)']:.4f}",
                        help="Deslocamento convertido em pontos"
                    )
                
                # Tabela principal das bandas
                st.write("### 📊 Bandas PTAX Calculadas")
                
                # Criar e exibir a tabela
                tabela_bandas = criar_tabela_bandas_ptax(bandas_ptax, qtde)
                
                if tabela_bandas is not None:
                    # Aplicar estilo à tabela
                    st.dataframe(
                        tabela_bandas,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Tipo de Banda": st.column_config.TextColumn(
                                "🎯 Tipo de Banda",
                                help="Tipo de banda calculada",
                                width="medium"
                            ),
                            **{f"PTAX {i}": st.column_config.NumberColumn(
                                f"💰 PTAX {i}",
                                help=f"Valores para PTAX {i}",
                                format="%.2f"
                            ) for i in range(1, qtde + 1)}
                        }
                    )
                    
                    # Adicionar explicação das bandas
                    with st.expander("ℹ️ Como interpretar as bandas"):
                        st.write("""
                        **Explicação das Bandas PTAX:**
                        
                        - **1ª Máxima/Mínima**: Bandas principais calculadas com base no deslocamento
                        - **2ª Máxima/Mínima**: Bandas secundárias com ajuste adicional (±0.5%)
                        
                        **Interpretação:**
                        - Valores **acima da 1ª Máxima**: Possível sobrecompra
                        - Valores **abaixo da 1ª Mínima**: Possível sobrevenda  
                        - **Entre as bandas**: Zona de negociação normal
                        """)
                        
                    # Resumo estatístico
                    if qtde >= 2:
                        st.write("### 📈 Resumo Estatístico")
                        
                        # Calcular médias das bandas
                        maximas_1 = [bandas_ptax[f'1ª Máxima PTAX{i}'] for i in range(1, qtde + 1)]
                        minimas_1 = [bandas_ptax[f'1ª Mínima PTAX{i}'] for i in range(1, qtde + 1)]
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric(
                                "📊 Média 1ª Máxima", 
                                f"{sum(maximas_1)/len(maximas_1):.2f}"
                            )
                        with col2:
                            st.metric(
                                "📊 Média 1ª Mínima", 
                                f"{sum(minimas_1)/len(minimas_1):.2f}"
                            )
                        with col3:
                            amplitude = (sum(maximas_1)/len(maximas_1)) - (sum(minimas_1)/len(minimas_1))
                            st.metric(
                                "📏 Amplitude Média", 
                                f"{amplitude:.2f}",
                                help="Diferença entre máxima e mínima médias"
                            )
                            
            else:
                st.warning("⚠️ Não foi possível calcular as bandas PTAX. Verifique se todos os dados necessários estão disponíveis.")
        else:
            st.warning("📭 Nenhuma cotação PTAX disponível no momento.")

if __name__ == "__main__":
    main()
