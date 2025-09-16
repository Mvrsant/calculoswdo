import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from bcb import PTAX
import os

# ==============================
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
        # Tenta carregar do caminho padrão
        if os.path.exists(DEFAULT_EXCEL_PATH):
            data = pd.read_excel(DEFAULT_EXCEL_PATH)
            st.success(f"Planilha carregada: {DEFAULT_EXCEL_PATH}")
        else:
            uploaded_file = st.file_uploader("📂 Selecione arquivo Excel:", type=["xlsx"])
            if not uploaded_file:
                return None
            data = pd.read_excel(uploaded_file)

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
        if os.path.exists(DEFAULT_EXCEL_PATH):
            df_b3 = pd.read_excel(DEFAULT_EXCEL_PATH, sheet_name="base_b3", header=None)
        else:
            uploaded_file = st.file_uploader("📂 Envie Excel com aba 'base_b3':", type=["xlsx"])
            if not uploaded_file:
                return None
            df_b3 = pd.read_excel(uploaded_file, sheet_name="base_b3", header=None)
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
        
        prices = df_dia['cotacaoVenda'].tolist()
        return prices[:4] + [None] * max(0, 4 - len(prices))
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
        base = ptax * 1000
        resultado.update({
            f"1ª Máxima PTAX{i}": round(base + deslocamento, 2),
            f"1ª Mínima PTAX{i}": round(base - deslocamento, 2),
            f"2ª Máxima PTAX{i}": round((base + deslocamento) * 1.005, 2),
            f"2ª Mínima PTAX{i}": round((base - deslocamento) * 0.995, 2),
        })
    return resultado

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
        for ticker_key, nome in [("cme", "CME - 6L"), ("brl_usd", "BRL/USD")]:
            cotacoes = obter_cotacoes_yfinance(TICKERS[ticker_key])
            df = criar_dataframe_cotacoes(cotacoes, nome)
            if df is not None:
                st.write(f"### {nome}")
                st.dataframe(df)

    with tab2:
        st.subheader("📄 Dados Carregados")
        if dados_excel:
            st.dataframe(dados_excel)
        else:
            st.warning("Não foi possível carregar os dados do Excel.")

    with tab3:
        # Paridade Ouro
        paridade_ouro = calcular_paridade_ouro(xauusd, valor_ouro_brl)
        st.subheader("⚖️ Paridade Ouro")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Ouro Spot", f"{xauusd:.2f}" if xauusd else "N/A")
        with col2:
            st.metric("Ouro R$", f"{valor_ouro_brl:.2f}" if valor_ouro_brl else "N/A")
        with col3:
            st.metric("Paridade", f"{paridade_ouro:.4f}" if paridade_ouro else "N/A")

        # Outros cálculos
        metricas = [
            ("💲 Abertura WDO", wdo_abertura, dxy_variacao),
            ("💹 Over (DI1)", over, None),
            ("💵 Preço Justo", preco_justo, None)
        ]
        
        for titulo, valor, extra in metricas:
            st.subheader(titulo)
            if valor is not None:
                st.metric("Valor", f"{valor:.4f}")
                if extra is not None:
                    st.write(f"Variação DXY: {extra}%")
            else:
                st.warning("Não foi possível calcular")

        # Bandas
        if all(x is not None for x in [wdo_abertura, over, sup_volb3]):
            bandas = calcular_bandas(wdo_abertura, over, sup_volb3)
            st.subheader("📊 Bandas de Máximas e Mínimas")
            st.metric("VOL B3", sup_volb3)
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"1ª Máxima: {bandas['1ª Máxima']}")
                st.write(f"2ª Máxima: {bandas['2ª Máxima']}")
            with col2:
                st.write(f"1ª Mínima: {bandas['1ª Mínima']}")
                st.write(f"2ª Mínima: {bandas['2ª Mínima']}")

    with tab4:
        ptax_validas = [p for p in ptax_cotacoes if p is not None]
        qtde = len(ptax_validas)
        
        st.subheader("🧾 Cotações PTAX")
        st.write(f"{qtde} de 4 cotações disponíveis")
        st.progress(qtde / 4)
        
        if qtde < 4:
            st.info("⏳ Aguardando próximas cotações...")
            
        # Exibe cotações
        if qtde > 0:
            cols = st.columns(qtde)
            for i, ptax in enumerate(ptax_validas):
                with cols[i]:
                    st.metric(f"PTAX {i+1}", f"{ptax:.4f}")

        # Bandas PTAX
        bandas_ptax = calcular_bandas_ptax(wdo_abertura, over, sup_volb3, ptax_cotacoes)
        if bandas_ptax:
            st.subheader("📊 Bandas PTAX")
            for i in range(qtde):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"1ª Máxima PTAX{i+1}: {bandas_ptax[f'1ª Máxima PTAX{i+1}']}")
                    st.write(f"2ª Máxima PTAX{i+1}: {bandas_ptax[f'2ª Máxima PTAX{i+1}']}")
                with col2:
                    st.write(f"1ª Mínima PTAX{i+1}: {bandas_ptax[f'1ª Mínima PTAX{i+1}']}")
                    st.write(f"2ª Mínima PTAX{i+1}: {bandas_ptax[f'2ª Mínima PTAX{i+1}']}")

if __name__ == "__main__":
    main()
