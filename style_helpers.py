import pandas as pd

def estilizar_tabela(df, cols_gradiente, cmap="PuBuGn", bold_cols=["Métrica"]):
    styled = df.style.background_gradient(subset=cols_gradiente, cmap=cmap)
    for col in bold_cols:
        styled = styled.set_properties(**{'font-weight': 'bold'}, subset=[col])
    return styled

def estilizar_bandas_ptax(df):
    col_max = [col for col in df.columns if "Máxima" in col]
    col_min = [col for col in df.columns if "Mínima" in col]
    return estilizar_tabela(df, col_max + col_min, cmap="Oranges", bold_cols=["Tipo de Banda"])
