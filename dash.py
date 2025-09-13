
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from bcb import PTAX
import os

# ==============================
# Configurações Globais
# ==============================
TICKERS = {
    "cme": "6L=F",
    "brl_usd": "BRLUSD=X",
    "xauusd": "GC=F",
    "dxy": "DX-Y.NYB"
}
URLS = {
    "gold_price_brl": "https://www.melhorcambio.com/ouro-hoje"
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0'
}
DEFAULT_EXCEL_PATH = pd.read_excel("ddeprofit.xlsx") #r"C:\Users\user\Documents\planilhas\ddeprofit.xlsx"

# ==============================
# Funções Auxiliares
# ==============================
def safe_execute(func, *args, error_message="Erro ao executar função", **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        st.error(f"{error_message}: {e}")
        return None

def extrair_valor(dataframe, ativo, coluna):
    filtro = dataframe.loc[dataframe['Asset'] == ativo, coluna]
    return filtro.iloc[0] if not filtro.empty else None

# ==============================
# Funções de Extração de Dados
# ==============================
def obter_cotacao_xauusd():
    try:
        ticker = yf.Ticker(TICKERS["xauusd"])
        historico = ticker.history(period="1d")
        return historico['Close'].iloc[-1] if not historico.empty else None
    except Exception as e:
        st.error(f"Erro ao obter cotação XAU/USD: {e}")
        return None

def obter_valor_grama_ouro_reais():
    try:
        response = requests.get(URLS["gold_price_brl"], headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        valor_grama = soup.find('input', {'id': 'comercial'}).get('value')
        return float(valor_grama.replace(',', '.'))
    except Exception as e:
        st.error(f"Erro ao obter valor do ouro: {e}")
        return None

def obter_variacao_dxy():
    try:
        ticker = yf.Ticker(TICKERS["dxy"])
        historico = ticker.history(period="5d")
        if len(historico) >= 2:
            fechamento_anterior = historico['Close'].iloc[-2]
            fechamento_atual = historico['Close'].iloc[-1]
            return round(((fechamento_atual - fechamento_anterior) / fechamento_anterior) * 100, 2)
        return None
    except Exception as e:
        st.error(f"Erro ao obter variação DXY: {e}")
        return None

# Função auxiliar para extrair valores da planilha
def extrair_valor(df, ativo, coluna):
    try:
        valor = df.loc[df['Asset'] == ativo, coluna].values[0]
        return float(valor)
    except:
        return None

# Função para calcular a data de vencimento do WDO
def calcular_vencimento_wdo(data_base):
    ano = data_base.year
    mes = data_base.month + 1 if data_base.month < 12 else 1
    ano = ano if data_base.month < 12 else ano + 1

    primeiro_dia = datetime(ano, mes, 1)

    # Se for dia útil, é o vencimento. Se não, pega o próximo dia útil.
    while primeiro_dia.weekday() >= 5:  # 5 = sábado, 6 = domingo
        primeiro_dia += timedelta(days=1)

    return primeiro_dia

# Função principal
def carregar_dados_excel():
    try:
        if os.path.exists(DEFAULT_EXCEL_PATH):
            data = pd.read_excel(DEFAULT_EXCEL_PATH)
            st.success(f"Planilha carregada automaticamente de: {DEFAULT_EXCEL_PATH}")
        else:
            uploaded_file = st.file_uploader(
                "📂 Arquivo não encontrado no caminho padrão. Selecione um arquivo Excel manualmente:",
                type=["xlsx"]
            )
            if uploaded_file is None:
                return None
            data = pd.read_excel(uploaded_file)

        required_columns = ['Asset', 'Fechamento Anterior', 'Último']
        if not all(col in data.columns for col in required_columns):
            st.warning("⚠️ Colunas ausentes no arquivo Excel")
            return None

        data['Asset'] = data['Asset'].str.strip()

        # Extração dos dados
        wdo_fut = extrair_valor(data, 'WDOFUT', 'Fechamento Anterior')
        dolar_spot = extrair_valor(data, 'USD/BRL', 'Fechamento Anterior')
        di1_fut = extrair_valor(data, 'DI1FUT', 'Último')
        frp0 = extrair_valor(data, 'FRP0', 'Último')

        # Datas
        current_date = datetime.today()
        expiration_date = calcular_vencimento_wdo(current_date)

        # Dias úteis restantes
        business_days = len(pd.bdate_range(start=current_date, end=expiration_date))

        return {
            "wdo_fut": wdo_fut,
            "dolar_spot": dolar_spot,
            "di1_fut": di1_fut,
            "frp0": frp0,
            "expiration_date": expiration_date.strftime('%d/%m/%Y'),
            "business_days_remaining": business_days
        }

    except Exception as e:
        st.error(f"Erro ao carregar Excel: {e}")
        return None

def extrair_sup_vol_b3_formatado():
    try:
        if os.path.exists(DEFAULT_EXCEL_PATH):
            df_b3 = pd.read_excel(DEFAULT_EXCEL_PATH, sheet_name="base_b3", header=None)
        else:
            uploaded_file = st.file_uploader(
                "📂 Arquivo não encontrado. Envie o Excel com aba 'base_b3' para extrair SUP_VOLB3:",
                type=["xlsx"]
            )
            if uploaded_file is None:
                return None
            df_b3 = pd.read_excel(uploaded_file, sheet_name="base_b3", header=None)
        return float(df_b3.iloc[18, 6])
    except Exception as e:
        st.error(f"Erro ao extrair SUP_VOLB3: {e}")
        return None


# ==============================
# Funções de Cálculo
# ==============================
def obter_cotacoes(ticker):
    try:
        ativo = yf.Ticker(ticker)
        historico = ativo.history(period="5d")
        if historico.empty or len(historico) < 1:
            st.warning(f"⚠️ Dados insuficientes para {ticker}.")
            return None
        abertura = historico['Open'].dropna().iloc[-1]
        maxima = historico['High'].dropna().iloc[-1]
        minima = historico['Low'].dropna().iloc[-1]
        fechamento = historico['Close'].dropna().iloc[-1]
        return abertura, maxima, minima, fechamento
    except Exception as e:
        st.error(f"Erro ao obter dados para {ticker}: {e}")
        return None

def calcular_paridade_ouro(xauusd, valor_grama_ouro_reais):
    if None in (xauusd, valor_grama_ouro_reais):
        return None
    gramas_por_onca = 31.1035
    return round((valor_grama_ouro_reais / (xauusd / gramas_por_onca)) * 1000, 4)

def calcular_abertura_wdo(wdo_fechamento, dxy_variacao):
    if None in (wdo_fechamento, dxy_variacao):
        return None
    return round(wdo_fechamento * (1 + dxy_variacao / 100), 4)

def calcular_over(di1_fut, business_days_remaining):
    if None in (di1_fut, business_days_remaining):
        return None
    return round(((1 + di1_fut)**(1/252) - 1) * business_days_remaining, 5)

def calcular_preco_justo(dolar_spot, over):
    if None in (dolar_spot, over):
        return None
    over_corrigido = over / 100
    return round(dolar_spot * (1 + over_corrigido), 4)

def calcular_max_min_abertura(wdo_abertura, over, sup_volb3):
    if None in (wdo_abertura, over, sup_volb3):
        return None
    over_bandas = over / 100
    deslocamento = (wdo_abertura * over_bandas) + sup_volb3
    primeira_max = wdo_abertura + deslocamento
    primeira_min = wdo_abertura - deslocamento
    segunda_max = primeira_max * 1.005
    segunda_min = primeira_min * 0.995
    return {
        "1ª Máxima": round(primeira_max, 2),
        "1ª Mínima": round(primeira_min, 2),
        "2ª Máxima": round(segunda_max, 2),
        "2ª Mínima": round(segunda_min, 2)
    }

def obter_cotacoes_ptax():
    try:
        ptax = PTAX()
        endpoint = ptax.get_endpoint('CotacaoMoedaPeriodo')
        data_consulta = datetime.today().date()
        while True:
            data_consulta_str = data_consulta.strftime('%m.%d.%Y')
            df = (endpoint.query()
                  .parameters(moeda='USD', dataInicial=data_consulta_str, dataFinalCotacao=data_consulta_str)
                  .collect())
            if not df.empty:
                break
            data_consulta -= timedelta(days=1)
        df['dataHoraCotacao'] = pd.to_datetime(df['dataHoraCotacao'])
        df_dia = df[df['dataHoraCotacao'].dt.date == data_consulta]
        df_dia = df_dia.sort_values(by='dataHoraCotacao').reset_index(drop=True)
        sale_prices = df_dia['cotacaoVenda'].tolist()
        return sale_prices[:4] + [None] * (4 - len(sale_prices))
    except Exception as e:
        st.error(f"Erro ao obter cotações da PTAX: {e}")
        return [None, None, None, None]

def calcular_bandas_ptax(wdo_abertura, over, sup_volb3, *ptaxes):
    if None in (wdo_abertura, over, sup_volb3):
        return None
    deslocamento_ptax = (wdo_abertura * (over/100)) + (sup_volb3)
    resultados = {
        "Deslocamento PTAX (em valor)": round(deslocamento_ptax, 5),
        "Deslocamento PTAX (em pontos)": round(deslocamento_ptax * 1000, 4)
    }
    for i, ptax in enumerate(ptaxes, start=1):
        if ptax is None:
            continue
        first_max = (ptax * 1000) + deslocamento_ptax
        first_min = (ptax * 1000) - deslocamento_ptax
        sec_max = first_max * 1.005
        sec_min = first_min * 0.995
        resultados.update({
            f"1ª Máxima PTAX{i}": round(first_max, 2),
            f"1ª Mínima PTAX{i}": round(first_min, 2),
            f"2ª Máxima PTAX{i}": round(sec_max, 2),
            f"2ª Mínima PTAX{i}": round(sec_min, 2),
        }
    )
    return resultados



# ==============================
# Interface Principal
# ==============================
def main():
    st.title("📈 Cálculos do contrato futuro de dólar ")
    wdo_abertura = None
    preco_justo = None
    over = None
    with st.spinner("Carregando dados..."):
        dados_excel = safe_execute(carregar_dados_excel)
        sup_volb3 = safe_execute(extrair_sup_vol_b3_formatado)
        xauusd = safe_execute(obter_cotacao_xauusd)
        valor_ouro_brl = safe_execute(obter_valor_grama_ouro_reais)
        dxy_variacao = safe_execute(obter_variacao_dxy)
        ptax_cotacoes = safe_execute(obter_cotacoes_ptax)

    # Removendo a aba "Resultados Calculados"
    aba_paridades_cme, aba_dados, aba_calculos_abertura, aba_Ptax = st.tabs(
        ["📉 Paridades CME/BRLUSD", "📊 Dados Carregados", "📈 Abertura Calculada", "🧾 Cotações PTAX"]
    )

    with aba_calculos_abertura:
        st.subheader("⚖️ Paridade XAU")
        paridade_ouro = calcular_paridade_ouro(xauusd, valor_ouro_brl)
        st.write("Ouro spot", xauusd)
        st.write( "Ouro R$", valor_ouro_brl)
        st.write(
            f"{paridade_ouro:.4f}" if paridade_ouro is not None
            else "Erro ao calcular a paridade do ouro."
        )
        if dados_excel is not None:
            di1_fut = dados_excel.get("di1_fut")
            business_days_remaining = dados_excel.get("business_days_remaining")
            dolar_spot = dados_excel.get("dolar_spot")
            wdo_abertura = calcular_abertura_wdo(dados_excel.get("wdo_fut"), dxy_variacao)
        st.subheader("💲 Abertura Estimada do WDO ")
        st.write(wdo_abertura)
        st.write ("Variação DXY", dxy_variacao)
        over = calcular_over(di1_fut, business_days_remaining)
        st.subheader("💹 Over (DI1 Futuro)")
        st.write(f"{over:.5f}" if over is not None else "Erro ao calcular o over.")
        preco_justo = calcular_preco_justo(dolar_spot, over)
        st.subheader("💵 Preço Justo do Dólar")
        st.write(f"R$ {preco_justo:.4f}" if preco_justo is not None else "Erro ao calcular o preço justo.")
        if sup_volb3 is not None and wdo_abertura is not None and over is not None:
            bandas_abertura = calcular_max_min_abertura(wdo_abertura, over, sup_volb3)
            st.subheader("📊 Bandas de Máximas e Mínimas para a Abertura")
            if bandas_abertura is not None:
                st.write("VOL B3", sup_volb3)
                st.write(f"1ª Máxima: {bandas_abertura['1ª Máxima']}")
                st.write(f"1ª Mínima: {bandas_abertura['1ª Mínima']}")
                st.write(f"2ª Máxima: {bandas_abertura['2ª Máxima']}")
                st.write(f"2ª Mínima: {bandas_abertura['2ª Mínima']}")
            else:
                st.warning("Erro ao calcular as bandas de máximas e mínimas.")

    with aba_paridades_cme:
        cme_ticker = "6L=F"
        brl_usd_ticker = "BRLUSD=X"
        cme_cotacoes = obter_cotacoes(cme_ticker)
        brl_usd_cotacoes = obter_cotacoes(brl_usd_ticker)
        if cme_cotacoes:
            cme_data = {
                "Métrica": ["Abertura", "Fechamento (Último)", "Máxima", "Mínima"],
                "Cotação (CME - 6L)": [cme_cotacoes[0], cme_cotacoes[3], cme_cotacoes[1], cme_cotacoes[2]]
            }
            cme_df = pd.DataFrame(cme_data)
            cme_df["Valor Calculado"] = (1 / cme_df["Cotação (CME - 6L)"] * 1000).round(2)
            st.write("### Conversões Calculadas para o par BRL/USD e Real CME (6L=F)")
            st.dataframe(cme_df)
        if brl_usd_cotacoes:
            brl_usd_data = {
                "Métrica": ["Abertura", "Fechamento (Último)", "Máxima", "Mínima"],
                "Cotação (BRL/USD)": [brl_usd_cotacoes[0], brl_usd_cotacoes[3], brl_usd_cotacoes[1], brl_usd_cotacoes[2]]
            }
            brl_usd_df = pd.DataFrame(brl_usd_data)
            brl_usd_df["Valor Calculado"] = (1 / brl_usd_df["Cotação (BRL/USD)"] * 1000).round(2)
            st.write("### Conversões Calculadas para o Par BRL/USD")
            st.dataframe(brl_usd_df)

    with aba_dados:
        st.subheader("📄 Dados Carregados")
        if dados_excel is not None:
            st.write("Dados da planilha:")
            st.dataframe(dados_excel)
        else:
            st.warning("Não foi possível carregar os dados do Excel.")

    with aba_Ptax:
        ptax_validas = [ptax for ptax in ptax_cotacoes if ptax is not None]
        qtde_disponivel = len(ptax_validas)
        st.subheader("🧾 Cotações PTAX disponíveis")
        st.write(f"{qtde_disponivel} de 4 cotações já disponíveis")
        st.progress(qtde_disponivel / 4)
        if qtde_disponivel < 4:
            st.info("⏳ Aguardando próximas cotações da PTAX... As bandas abaixo são parciais.")
        cols = st.columns(qtde_disponivel if qtde_disponivel > 0 else 1)
        for i, ptax in enumerate(ptax_validas, start=1):
            with cols[i - 1]:
                st.metric(label=f"PTAX {i}", value=f"{ptax:.4f}")
        bandas_ptax = calcular_bandas_ptax(wdo_abertura, over, sup_volb3, *ptax_cotacoes)
        if bandas_ptax:
            st.subheader("📊 Bandas PTAX calculadas")
            for i in range(qtde_disponivel):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"1ª Máxima PTAX{i+1}: {bandas_ptax[f'1ª Máxima PTAX{i+1}']}")
                    st.write(f"2ª Máxima PTAX{i+1}: {bandas_ptax[f'2ª Máxima PTAX{i+1}']}")
                with col2:
                    st.write(f"1ª Mínima PTAX{i+1}: {bandas_ptax[f'1ª Mínima PTAX{i+1}']}")
                    st.write(f"2ª Mínima PTAX{i+1}: {bandas_ptax[f'2ª Mínima PTAX{i+1}']}")
        else:
            st.warning("⚠️ Não foi possível calcular as bandas PTAX. Verifique os dados.")



# ==============================
# Execução do Programa
# ==============================
if __name__ == "__main__":

    main()


