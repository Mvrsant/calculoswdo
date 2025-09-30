import requests
import pandas as pd
import yfinance as yf
import numpy as np
import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from bcb import PTAX
import os

# Copie suas funções aqui:
TICKERS = {
    "cme": "6L=F", "brl_usd": "BRLUSD=X", 
    "xauusd": "GC=F", "dxy": "DX-Y.NYB"
}
def baixar_planilha_github(url, caminho_destino):
    try:
        resposta = requests.get(url)
        if resposta.status_code == 200:
            with open(caminho_destino, 'wb') as f:
                f.write(resposta.content)
            return True
        else:
            return False
    except Exception:
        return False

def safe_execute(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception:
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
    except Exception:
        return None

def obter_valor_grama_ouro_reais():
    try:
        response = requests.get("https://www.melhorcambio.com/ouro-hoje", headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
        valor = soup.find('input', {'id': 'comercial'}).get('value')
        return float(valor.replace(',', '.'))
    except Exception:
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
# Inclua também criar_dataframe_cotacoes, calcular_bandas, calcular_bandas_ptax e todas as funções de cálculo do seu código original aqui!
