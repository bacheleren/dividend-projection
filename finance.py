import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as object_patch

st.set_page_config(page_title="Valuation por Dividendos", layout="wide")

st.title("📊 Precificação e Projeção Dinâmica de Dividendos")
st.markdown("Este painel calcula o histórico completo, os dividendos parciais do ano corrente com projeção de fechamento, e a estimativa para o próximo ano.")

# Layout com duas colunas para o Input e o Botão de Atualização
col_input, col_botao = st.columns([3, 1])

with col_input:
    ticker_input = st.text_input("Digite o Ticker (sem .SA):", value="BBAS3").strip().upper()

with col_botao:
    st.write(" ") # Espaçadores visuais para alinhar o botão ao input
    st.write(" ")
    atualizar = st.button("🔄 Atualizar Dados")

if ticker_input:
    ticker_sa = f"{ticker_input}.SA"
    
    try:
        # A busca ocorre sempre que o script roda (ou quando o botão de atualizar é clicado)
        ticker = yf.Ticker(ticker_sa)
        info = ticker.info
        
        preco_atual = info.get('currentPrice') or info.get('regularMarketPrice')
        
        if not preco_atual:
            st.error("Não foi possível obter a cotação atual deste ativo. Verifique se o ticker está correto.")
        else:
            # Captura o momento exato da consulta dos dados
            horario_atualizacao = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            # Exibição do preço e do timestamp lado a lado
            col_preco, col_time = st.columns([1, 2])
            with col_preco:
                st.metric(label=f"Preço Atual de {ticker_input}", value=f"R$ {preco_atual:.2f}")
            with col_time:
                st.write(" ") # Alinhamento vertical com a métrica
                st.write(" ")
                st.caption(f"🕒 **Dados sincronizados em:** {horario_atualizacao}")
            
            # Definição dos anos com base no ano corrente
            ano_atual = datetime.datetime.now().year
            anos_historicos = list(range(ano_atual - 5, ano_atual)) 
            ano_seguinte = ano_atual + 1 
            
            # --- PROCESSAMENTO DOS DIVIDENDOS PAGOS ---
            dividendos = ticker.dividends
            dados_pagos = {ano: 0.0 for ano in anos_historicos}
            pago_ano_atual = 0.0
            
            if not dividendos.empty:
                df_div = dividendos.to_frame().reset_index()
                df_div['Ano'] = df_div['Date'].dt.year
                div_por_ano = df_div.groupby('Ano')['Dividends'].sum()
                
                for ano in anos_historicos:
                    dados_pagos[ano] = float(div_por_ano.get(ano, 0.0))
                
                pago_ano_atual = float(div_por_ano.get(ano_atual, 0.0))
            
            # --- CONFIGURAÇÕES DE PROJEÇÃO (INTERFACE) ---
            st.subheader("Parâmetros para Projeção Futura")
            payout_simulado = st.slider("Payout Estimado (%)", min_value=10, max_value=100, value=50, step=5) / 100.0
            yield_desejado = st.slider("Dividend Yield Mínimo Desejado (%)", min_value=4.0, max_value=12.0, value=6.0, step=0.5) / 100.0
            
            # --- PROJEÇÃO ANO ATUAL ---
            lpa_atual_est = info.get('trailingEps') or (preco_atual * 0.1)
            total_est_ano_atual = lpa_atual_est * payout_simulado
            restante_ano_atual = max(0.0, total_est_ano_atual - pago_ano_atual)
            
            # --- PROJEÇÃO PRÓXIMO ANO ---
            lpa_projetado_proximo = info.get('forwardEps') or (lpa_atual_est * 1.05)
            dividendo_ano_seguinte_projetado = lpa_projetado_proximo * payout_simulado
            
            # --- CONSTRUÇÃO DO GRÁFICO DE BARRAS EMPILHADAS ---
            anos_grafico = [str(ano) for ano in anos_historicos] + [str(ano_atual), f"{ano_seguinte} (Projetado)"]
            
            valores_historicos = [dados_pagos[ano] for ano in anos_historicos] + [pago_ano_atual, 0.0]
            valores_restante_ano = [0.0] * len(anos_historicos) + [restante_ano_atual, 0.0]
            valores_proximo_ano = [0.0] * len(anos_historicos) + [0.0, dividendo_ano_seguinte_projetado]
            
            fig = object_patch.Figure()
            
            fig.add_trace(object_patch.Bar(
                x=anos_grafico, y=valores_historicos, 
                name="Histórico / Pago no Ano", marker_color='#4682B4'
            ))
            fig.add_trace(object_patch.Bar(
                x=anos_grafico, y=valores_restante_ano, 
                name="Projeção Restante (Ano Atual)", marker_color='#FFA500'
            ))
            fig.add_trace(object_patch.Bar(
                x=anos_grafico, y=valores_proximo_ano, 
                name="Projeção Próximo Ano", marker_color='#2E8B57'
            ))
            
            fig.update_layout(
                barmode='stack',
                title=f"Evolução de Proventos e Projeções - {ticker_input}",
                xaxis_title="Ano",
                yaxis_title="Dividendos por Ação (R$)",
                template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # --- VALUATION (PREÇO TETO) ---
            preco_teto = dividendo_ano_seguinte_projetado / yield_desejado
            margem_seguranca = ((preco_teto / preco_atual) - 1) * 100
            
            st.subheader(f"Análise de Preço-Teto para {ano_seguinte}")
            col1, col2, col3 = st.columns(3)
            col1.metric(f"Div. Projetado ({ano_seguinte})", f"R$ {dividendo_ano_seguinte_projetado:.2f}")
            col2.metric("Preço-Teto Máximo", f"R$ {preco_teto:.2f}")
            
            if margem_seguranca > 0:
                col3.metric("Margem de Segurança", f"{margem_seguranca:.1f}%", delta="Descontada (Abaixo do Teto)")
            else:
                col3.metric("Margem de Segurança", f"{margem_seguranca:.1f}%", delta="Cara (Acima do Teto)", delta_color="inverse")
                
    except Exception as e:
        st.error(f"Erro ao processar dados do ticker {ticker_input}: {e}")
