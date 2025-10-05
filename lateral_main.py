import streamlit as st
import pandas as pd
import numpy as np

from lateral_financial_data import (

    safe_execute,
    carregar_dados_excel,
    extrair_sup_vol_b3,
    obter_cotacoes_yfinance,
    obter_valor_grama_ouro_reais,
    obter_variacao_dxy,
    obter_cotacoes_ptax,
    calcular_abertura_wdo,
    calcular_over,
    calcular_preco_justo,
    calcular_paridade_ouro,
    calcular_bandas,
    calcular_bandas_ptax,
    criar_tabela_bandas_ptax,
    exibir_metricas_ptax,      
)

from style_helpers import estilizar_tabela, estilizar_bandas_ptax
TICKERS = {
    "xauusd": "GC=F",
    "cme": "6L=F",
    "brl_usd": "BRLUSD=X"
}      

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

st.set_page_config(page_title="Cálculos WDO", page_icon= "💰", layout="wide")

def main():
    st.title("📈 Cálculos WDO - Mini Contrato Futuro de Dólar em Reais")

    # Carregamento de dados
    with st.spinner("Carregando dados..."):
        dados_excel = safe_execute(carregar_dados_excel)
        sup_volb3 = safe_execute(extrair_sup_vol_b3)
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

    # Sidebar para navegação
    menu = st.sidebar.radio(
        "Navegação",
        [
            "📈 Abertura Calculada",
            "📉 Paridades CME/BRLUSD",
            "📊 Dados Carregados",
            "🧾 Cotações PTAX"
        ]
    )

    if menu == "📉 Paridades CME/BRLUSD":
        for ticker_key, nome in [("cme", "CME - 6L"), ("brl_usd", "BRL/USD")]:
            cotacoes = obter_cotacoes_yfinance(TICKERS[ticker_key])
            df = criar_dataframe_cotacoes(cotacoes, nome)
            if df is not None:
                # Convert any date columns to datetime for Arrow compatibility
                import warnings
                for col in df.columns:
                    if df[col].dtype == object:
                        try:
                            df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', dayfirst=True)
                        except Exception:
                            try:
                                with warnings.catch_warnings():
                                    warnings.filterwarnings("ignore", category=UserWarning, message="Could not infer format*")
                                    df[col] = pd.to_datetime(df[col])
                            except Exception:
                                pass
                st.write(f"### {nome}")
                st.dataframe(df)

    elif menu == "📊 Dados Carregados":
        st.subheader("📄 Dados Carregados")
        if dados_excel is not None:
            # Exibir dados carregados em formato amigável
            labels = {
                "wdo_fut": "WDO Futuro (Fechamento Anterior)",
                "dolar_spot": "Dólar Spot (Fechamento Anterior)",
                "di1_fut": "DI1 Futuro (Último)",
                "frp0": "FRP0 (Último)",
                "expiration_date": "Data de Vencimento",
                "business_days_remaining": "Dias Úteis Restantes"
            }
            if isinstance(dados_excel, dict):
                tabela = pd.DataFrame({
                    "Descrição": [labels.get(k, k) for k in dados_excel.keys()],
                    "Valor": [
                        f"{v:.4f}" if k == "dolar_spot" and isinstance(v, float)
                        else f"{v:.2f}" if isinstance(v, float)
                        else str(v)
                        for k, v in dados_excel.items()
                    ]
                })
                tabela["Valor"] = tabela["Valor"].astype(str)
                st.dataframe(estilizar_tabela(tabela, ["Valor"]), width="stretch")
            elif isinstance(dados_excel, pd.DataFrame):
                st.dataframe(estilizar_tabela(dados_excel, list(dados_excel.columns)), width="stretch")
            else:
                st.write(dados_excel)
        else:
            st.warning("Não foi possível carregar os dados do Excel.")

    elif menu == "📈 Abertura Calculada":
        #bandas de máximas e mínimas
        if all(x is not None for x in [wdo_abertura, over, sup_volb3]):
            bandas = calcular_bandas(wdo_abertura, over, sup_volb3)
            df_bandas = pd.DataFrame({
                # "COTAÇOES DE INTERESSE WDO": [
                #     "Previsão de Abertura WDO",
                #     "1ª Máxima",
                #     "1ª Mínima",
                #     "2ª Máxima",
                #     "2ª Mínima"
                # ],
                # "Valor": [
                #     f"{wdo_abertura:.2f}",
                #     f"{bandas['1ª Máxima']:.2f}",
                #     f"{bandas['1ª Mínima']:.2f}",
                #     f"{bandas['2ª Máxima']:.2f}",
                #     f"{bandas['2ª Mínima']:.2f}"
                # ],

                "Previsão de Abertura WDO":[
                    f"{wdo_abertura:.2f}",
                    f"VOL B3 {sup_volb3:.2f}"           
                ],

                "mínimas": [
                    f"{bandas['1ª Mínima']:.2f}",
                    f"{bandas['2ª Mínima']:.2f}"
                ], 
                "máximas": [
                    f"{bandas['1ª Máxima']:.2f}",
                    f"{bandas['2ª Máxima']:.2f}"
                ]

            })

            st.dataframe(estilizar_bandas_ptax(df_bandas), width="stretch")
        
        paridade_ouro = calcular_paridade_ouro(xauusd, valor_ouro_brl)
        st.subheader("📈 Abertura Calculada e Paridade Ouro")
        tabelas_metricas = pd.DataFrame({
            'Métrica': [
                "Ouro Spot (USD)", "Ouro (R$)", "Paridade Ouro", 
                #"Abertura WDO", 
                "Variação DXY", "Over (DI1)", "Preço Justo"
            ],
            'Valor': [
                f"{xauusd:.2f}" if xauusd else "N/A",
                f"{valor_ouro_brl:.2f}" if valor_ouro_brl else "N/A",
                f"{paridade_ouro:.2f}" if paridade_ouro else "N/A",
                #f"{wdo_abertura:.2f}" if wdo_abertura else "N/A",
                f"{dxy_variacao:.2f}%" if dxy_variacao else "N/A",
                f"{over:.5f}" if over else "N/A",
                f"{preco_justo:.4f}" if preco_justo else "N/A"
            ]
        })

        
        st.dataframe(estilizar_tabela(tabelas_metricas, ["Valor"]), width="stretch")
                                                         
        
    elif menu == "🧾 Cotações PTAX":
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
            st.divider()
            bandas_ptax = calcular_bandas_ptax(wdo_abertura, over, sup_volb3, ptax_cotacoes)
            if bandas_ptax:
                # st.write("### 📐 Parâmetros de Cálculo")
                # col1, col2 = st.columns(2)
                # with col1:
                #     st.metric(
                #         "🎯 Deslocamento (Valor)", 
                #         f"{bandas_ptax['Deslocamento PTAX (valor)']:.5f}",
                #         help="Deslocamento base usado no cálculo das bandas"
                #     )
                # with col2:
                #     st.metric(
                #         "📍 Deslocamento (Pontos)", 
                #         f"{bandas_ptax['Deslocamento PTAX (pontos)']:.4f}",
                #         help="Deslocamento convertido em pontos"
                #     )
                st.write("### 📊 Bandas PTAX Calculadas")
                tabela_bandas = criar_tabela_bandas_ptax(bandas_ptax, qtde)
                if tabela_bandas is not None:
                    st.dataframe(
                        tabela_bandas,
                        width='stretch',
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
                    # 
                    
            else:
                st.warning("⚠️ Não foi possível calcular as bandas PTAX. Verifique se todos os dados necessários estão disponíveis.")
        else:
            st.warning("📭 Nenhuma cotação PTAX disponível no momento.")
            

if __name__ == "__main__":
    main()
