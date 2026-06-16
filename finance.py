import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as object_patch

st.set_page_config(page_title="Valuation por Dividendos", layout="wide")

st.title("📊 Precificação e Projeção de Dividendos")
st.markdown("Insira o ticker de uma ação da B3 (ex: `BBAS3`, `VALE3`, `PETR4`) para visualizar o histórico e o preço-teto projetado.")

# Input do usuário
ticker_input = st.text_input("Digite o Ticker (sem .SA):", value="BBAS3").strip().upper()

if ticker_input:
    ticker_sa = f"{ticker_input}.SA"
    
    try:
        # Busca dados do Yahoo Finance
        ticker = yf.Ticker(ticker_sa)
        info = ticker.info
        
        # 1. Informações de Preço Atual
        preco_atual = info.get('currentPrice') or info.get('regularMarketPrice')
        
        if not preco_atual:
            st.error("Não foi possível obter a cotação atual deste ativo. Verifique se o ticker está correto.")
        else:
            st.metric(label=f"Preço Atual de {ticker_input}", value=f"R$ {preco_atual:.2f}")
            
            # --- CAPTURA DE DADOS (HISTÓRICO) ---
            dividendos = ticker.dividends
            ano_atual = datetime.datetime.now().year
            
            # Filtrar últimos 5 anos completos (excluindo o ano atual para não pegar dados parciais)
            anos_historico = list(range(ano_atual - 5, ano_atual))
            
            dados_historicos = {}
            if not dividendos.empty:
                df_div = dividendos.to_frame().reset_index()
                df_div['Ano'] = df_div['Date'].dt.year
                # Agrupa por ano e soma os dividendos pagos
                div_por_ano = df_div.groupby('Ano')['Dividends'].sum()
                for ano in anos_historico:
                    dados_historicos[ano] = float(div_por_ano.get(ano, 0.0))
            else:
                for ano in anos_historico:
                    dados_historicos[ano] = 0.0
            
            # --- CAPTURA DE DADOS (PROJEÇÃO FUTURA) ---
            # O Yahoo Finance fornece o consenso de analistas para o Lucro Por Ação do próximo ano (forwardEps)
            lpa_projetado = info.get('forwardEps')
            
            st.subheader("Configurações de Projeção futura")
            # Deixamos o usuário ajustar o payout simulado para o próximo ano
            payout_simulado = st.slider("Payout Estimado para o Próximo Ano (%)", min_value=10, max_value=100, value=50, step=5) / 100.0
            yield_desejado = st.slider("Dividend Yield Mínimo Desejado (%)", min_value=4.0, max_value=12.0, value=6.0, step=0.5) / 100.0
            
            # Calcula o dividendo projetado com base no lucro futuro e payout do usuário
            if lpa_projetado and lpa_projetado > 0:
                dividendo_projetado = lpa_projetado * payout_simulado
                projecao_real = True
            else:
                # Se o Yahoo não tiver a projeção (comum em empresas menores), usamos a média histórica como aproximação
                valores_validos = [v for v in dados_historicos.values() if v > 0]
                dividendo_projetado = sum(valores_validos) / len(valores_validos) if valores_validos else 0.0
                projecao_real = False
                st.warning("⚠️ Projeção do mercado indisponível para este ativo. Usando a média histórica dos dividendos como estimativa.")
            
            # --- CONSTRUÇÃO DO GRÁFICO ---
            anos_grafico = [str(ano) for ano in anos_historico] + [f"{ano_atual + 1} (Projetado)"]
            valores_grafico = [dados_historicos[ano] for ano in anos_historico] + [dividendo_projetado]
            
            # Cores diferentes para diferenciar o histórico da projeção
            cores = ['#4682B4'] * 5 + ['#2E8B57']
            
            fig = object_patch.Figure(data=[
                object_patch.Bar(x=anos_grafico, y=valores_grafico, marker_color=cores, text=[f"R$ {v:.2f}" for v in valores_grafico], textposition='auto')
            ])
            
            fig.update_layout(
                title=f"Histórico e Projeção de Dividendos por Ação - {ticker_input}",
                xaxis_title="Ano",
                yaxis_title="Dividendos (R$)",
                template="plotly_white"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # --- CÁLCULO DE VALUATION (VALOR JUSTO / PREÇO TETO) ---
            preco_teto = dividendo_projetado / yield_desejado
            margem_seguranca = ((preco_teto / preco_atual) - 1) * 100
            
            st.subheader("Análise de Preço-Teto (Método de Bazin)")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Dividendo Projetado (Próximo Ano)", f"R$ {dividendo_projetado:.2f}")
            col2.metric("Preço-Teto Máximo", f"R$ {preco_teto:.2f}")
            
            if margem_seguranca > 0:
                col3.metric("Margem de Segurança", f"{margem_seguranca:.1f}%", delta="Descontada (Abaixo do Teto)")
            else:
                col3.metric("Margem de Segurança", f"{margem_seguranca:.1f}%", delta="Cara (Acima do Teto)", delta_color="inverse")
                
    except Exception as e:
        st.error(f"Erro ao processar o ticker. Certifique-se de digitar um código válido na B3. Detalhes: {e}")