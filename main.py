import streamlit as st
import pandas as pd
import numpy as np

from financial_data import (
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
    criar_dataframe_cotacoes
)
from style_helpers import estilizar_tabela, estilizar_bandas_ptax

def main():
    st.set_page_config(page_title="Cálculos WDO", layout="wide")
    st.title("📈 Cálculos WDO - Mini Contrato Futuro de Dólar")

    with st.spinner("Carregando dados..."):
        dados_excel = safe_execute(carregar_dados_excel)
        sup_volb3 = safe_execute(extrair_sup_vol_b3)
        xauusd_data = obter_cotacoes_yfinance("GC=F")
        xauusd = xauusd_data['close'] if xauusd_data else None
        valor_ouro_brl = safe_execute(obter_valor_grama_ouro_reais)
        dxy_variacao = safe_execute(obter_variacao_dxy)
        ptax_cotacoes = safe_execute(obter_cotacoes_ptax)

    wdo_abertura = over = preco_justo = None
    if dados_excel:
        wdo_abertura = calcular_abertura_wdo(dados_excel.get("wdo_fut"), dxy_variacao)
        over = calcular_over(dados_excel.get("di1_fut"), dados_excel.get("business_days_remaining"))
        preco_justo = calcular_preco_justo(dados_excel.get("dolar_spot"), over)

    menu = st.sidebar.radio(
        "ABAS",
        [
            "📉 Paridades CME/BRLUSD",
            "📊 Dados Carregados",
            "📈 Abertura Calculada",
            "🧾 Cotações PTAX"
        ]
    )

    # Paridades CME/BRLUSD
    if menu == "📉 Paridades CME/BRLUSD":
        for ticker_key, nome in [("cme", "CME - 6L"), ("brl_usd", "BRL/USD")]:
            cotacoes = obter_cotacoes_yfinance(ticker_key)
            df = criar_dataframe_cotacoes(cotacoes, nome)
            if df is not None:
                st.write(f"### {nome}")
                st.dataframe(estilizar_tabela(df, [f"Cotação ({nome})", "Valor Calculado"]), width="stretch")
        pass


    # Dados Carregados
    elif menu == "📊 Dados Carregados":
        st.subheader("📄 Dados Carregados")
        if dados_excel:
            st.dataframe(estilizar_tabela(pd.DataFrame([dados_excel]), list(dados_excel.keys()), cmap="Blues"), width='stretch')
        else:
            st.warning("Não foi possível carregar os dados do Excel.")

    # Abertura Calculada
    elif menu == "📈 Abertura Calculada":
        paridade_ouro = calcular_paridade_ouro(xauusd, valor_ouro_brl)
        st.subheader("⚖️ Resultados - Abertura Calculada e Paridade Ouro")
        tabela_metricas = pd.DataFrame({
            'Métrica': [
                "Ouro Spot (USD)", "Ouro (R$)", "Paridade Ouro",
                "Abertura WDO", "Variação DXY", "Over (DI1)", "Preço Justo"
            ],
            'Valor': [
                f"{xauusd:.2f}" if xauusd else "N/A",
                f"{valor_ouro_brl:.2f}" if valor_ouro_brl else "N/A",
                f"{paridade_ouro:.2f}" if paridade_ouro else "N/A",
                f"{wdo_abertura:.2f}" if wdo_abertura else "N/A",
                f"{dxy_variacao:.2f}%" if dxy_variacao else "N/A",
                f"{over:.5f}" if over else "N/A",
                f"{preco_justo:.4f}" if preco_justo else "N/A"
            ]
        })
        st.dataframe(estilizar_tabela(tabela_metricas, ["Valor"]), width="stretch")

        # Bandas de máximas e mínimas
    if all(x is not None for x in [wdo_abertura, over, sup_volb3]):
            bandas = calcular_bandas(wdo_abertura, over, sup_volb3)
            df_bandas = pd.DataFrame({
                "Tipo de Banda": ["1ª Máxima", "1ª Mínima", "2ª Máxima", "2ª Mínima"],
                "Valor": [bandas['1ª Máxima'], bandas['1ª Mínima'], bandas['2ª Máxima'], bandas['2ª Mínima']]
            })
            st.dataframe(estilizar_bandas_ptax(df_bandas), width="stretch")

    # Cotações PTAX
    elif menu == "🧾 Cotações PTAX":
        ptax_validas = [p for p in ptax_cotacoes if p is not None]
        qtde = len(ptax_validas)
        st.subheader("🧾 Cotações PTAX do Dia")
        st.metric("Disponibilidade", f"{qtde}/4")
        st.progress(qtde / 4)
        if qtde > 0:
            st.write("### 💰 Cotações Atuais")
            exibir_metricas_ptax(ptax_validas)
            bandas_ptax = calcular_bandas_ptax(wdo_abertura, over, sup_volb3, ptax_cotacoes)
            tabela_bandas = criar_tabela_bandas_ptax(bandas_ptax, qtde)
            if tabela_bandas is not None:
                st.dataframe(estilizar_bandas_ptax(tabela_bandas), width="stretch")
                # Explicação interpretativa (igual ao seu modelo original)
                with st.expander("ℹ️ Como interpretar as bandas"):
                    st.write("""
                    **Explicação das Bandas PTAX:**\n
                    - **1ª Máxima/Mínima**: Bandas principais calculadas com base no deslocamento
                    - **2ª Máxima/Mínima**: Bandas secundárias com ajuste adicional (±0.5%)
                    **Interpretação:**
                    - Valores **acima da 1ª Máxima**: Possível sobrecompra
                    - Valores **abaixo da 1ª Mínima**: Possível sobrevenda
                    - **Entre as bandas**: Zona de negociação normal
                    """)
            # Resumo estatístico igual ao seu original
            if qtde >= 2 and bandas_ptax:
                st.write("### 📈 Resumo Estatístico")
                maximas_1 = [bandas_ptax.get(f'1ª Máxima PTAX{i}') for i in range(1, qtde + 1)]
                minimas_1 = [bandas_ptax.get(f'1ª Mínima PTAX{i}') for i in range(1, qtde + 1)]
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Média 1ª Máxima", f"{np.nanmean(maximas_1):.2f}")
                with col2:
                    st.metric("Média 1ª Mínima", f"{np.nanmean(minimas_1):.2f}")
                with col3:
                    amplitude = np.nanmean(maximas_1) - np.nanmean(minimas_1)
                    st.metric("Amplitude Média", f"{amplitude:.2f}", help="Diferença média")

if __name__ == "__main__":
    main()
