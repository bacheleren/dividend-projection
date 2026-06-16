import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Valuation por Dividendos", layout="wide")

st.title("📊 Precificação e Projeção Dinâmica de Dividendos")

# Isola a chamada em uma função com cache do Streamlit (Validade de 1 hora)
@st.cache_data(ttl=3600, show_spinner="Sincronizando dados com o mercado...")
def buscar_dados_api(ticker_str):
    ticker = yf.Ticker(ticker_str)
    info = ticker.info
    dividendos = ticker.dividends
    # Puxamos os demonstrativos financeiros para achar o Lucro Por Ação (EPS) histórico
    financials = ticker.financials 
    
    horario_busca = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return info, dividendos, financials, horario_busca

ticker_input = st.text_input("Digite o Ticker (sem .SA):", value="BBAS3").strip().upper()

if ticker_input:
    ticker_sa = f"{ticker_input}.SA"
    
    try:
        info, dividendos, financials, horario_atualizacao = buscar_dados_api(ticker_sa)
        
        preco_atual = info.get('currentPrice') or info.get('regularMarketPrice')
        
        if not preco_atual:
            st.error("Não foi possível obter a cotação atual deste ativo. Verifique se o ticker está correto.")
        else:
            col_preco, col_time = st.columns([1, 2])
            with col_preco:
                st.metric(label=f"Preço Atual de {ticker_input}", value=f"R$ {preco_atual:.2f}")
            with col_time:
                st.write(" ")
                st.write(" ")
                st.caption(f"🕒 **Última sincronização:** {horario_atualizacao} (Cache ativo)")
            
            ano_atual = datetime.datetime.now().year
            anos_historicos = list(range(ano_atual - 5, ano_atual)) 
            ano_seguinte = ano_atual + 1 
            
            # --- PROCESSAMENTO DOS DIVIDENDOS ---
            dados_pagos = {ano: 0.0 for ano in anos_historicos}
            pago_ano_atual = 0.0
            
            if not dividendos.empty:
                df_div = dividendos.to_frame().reset_index()
                df_div['Ano'] = df_div['Date'].dt.year
                div_por_ano = df_div.groupby('Ano')['Dividends'].sum()
                
                for ano in anos_historicos:
                    dados_pagos[ano] = float(div_por_ano.get(ano, 0.0))
                pago_ano_atual = float(div_por_ano.get(ano_atual, 0.0))
            
            # --- PROCESSAMENTO DO PAYOUT HISTÓRICO ---
            eps_historico = {}
            if financials is not None and not financials.empty:
                # Procura a linha de EPS (Lucro por Ação) básico ou diluído
                for eps_label in ['Basic EPS', 'Diluted EPS']:
                    if eps_label in financials.index:
                        eps_row = financials.loc[eps_label]
                        for data_balanco, eps_val in eps_row.items():
                            if pd.notna(eps_val):
                                eps_historico[data_balanco.year] = float(eps_val)
                        break

            payouts_anuais = {}
            payouts_validos = []
            
            for ano in anos_historicos:
                div = dados_pagos[ano]
                eps = eps_historico.get(ano, 0.0)
                
                if eps > 0 and div > 0: # Só calcula se houve lucro e distribuição
                    payout = div / eps
                    # Evita distorções bizarras de dados (ex: payout > 200%)
                    payout_real = min(payout, 2.0) 
                    payouts_anuais[ano] = payout_real
                    payouts_validos.append(payout_real)
                else:
                    payouts_anuais[ano] = None

            # Calcula a média para o slider
            if payouts_validos:
                media_payout_hist = sum(payouts_validos) / len(payouts_validos)
            else:
                # Fallback: Tenta pegar o payout atual do info, ou fixa em 50%
                media_payout_hist = info.get('payoutRatio', 0.5) or 0.5
            
            # Formata para % e garante que fique entre os limites do slider
            media_payout_pct = int(round(media_payout_hist * 100))
            media_payout_pct = min(max(media_payout_pct, 10), 100)

            # --- PARÂMETROS ---
            st.subheader("Parâmetros para Projeção Futura")
            # Agora o slider já nasce com a média histórica calculada!
            payout_simulado = st.slider(
                f"Payout Estimado (%) - Base Histórica: {media_payout_pct}%", 
                min_value=10, max_value=100, value=media_payout_pct, step=5
            ) / 100.0
            
            yield_desejado = st.slider("Dividend Yield Mínimo Desejado (%)", min_value=4.0, max_value=12.0, value=6.0, step=0.5) / 100.0
            
            # --- PROJEÇÕES ---
            lpa_atual_est = info.get('trailingEps') or (preco_atual * 0.1)
            total_est_ano_atual = lpa_atual_est * payout_simulado
            restante_ano_atual = max(0.0, total_est_ano_atual - pago_ano_atual)
            
            lpa_projetado_proximo = info.get('forwardEps') or (lpa_atual_est * 1.05)
            dividendo_ano_seguinte_projetado = lpa_projetado_proximo * payout_simulado
            
            # --- GRÁFICO COM TEXTOS INTERNOS ---
            # Cria os labels do eixo X incluindo o Payout entre parênteses
            anos_grafico = []
            for ano in anos_historicos:
                payout_ano = payouts_anuais.get(ano)
                if payout_ano is not None:
                    anos_grafico.append(f"{ano}<br>({payout_ano * 100:.0f}%)")
                else:
                    anos_grafico.append(str(ano))
                    
            anos_grafico.extend([str(ano_atual), f"{ano_seguinte} (Proj)"])
            
            valores_historicos = [dados_pagos[ano] for ano in anos_historicos] + [pago_ano_atual, 0.0]
            valores_restante_ano = [0.0] * len(anos_historicos) + [restante_ano_atual, 0.0]
            valores_proximo_ano = [0.0] * len(anos_historicos) + [0.0, dividendo_ano_seguinte_projetado]
            
            def format_text(valores):
                return [f"R$ {v:.2f}" if v > 0 else "" for v in valores]

            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=anos_grafico, y=valores_historicos, name="Histórico / Pago", 
                marker_color='#4682B4', text=format_text(valores_historicos), textposition='auto'
            ))
            fig.add_trace(go.Bar(
                x=anos_grafico, y=valores_restante_ano, name="Projeção Restante (Ano Atual)", 
                marker_color='#FFA500', text=format_text(valores_restante_ano), textposition='auto'
            ))
            fig.add_trace(go.Bar(
                x=anos_grafico, y=valores_proximo_ano, name="Projeção Próximo Ano", 
                marker_color='#2E8B57', text=format_text(valores_proximo_ano), textposition='auto'
            ))
            
            fig.update_layout(
                barmode='stack', title=f"Evolução de Proventos e Payout Histórico - {ticker_input}",
                xaxis_title="Ano (Payout Realizado)", yaxis_title="Dividendos por Ação (R$)", template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # --- VALUATION DINÂMICO (DROPDOWN) ---
            st.subheader("Cálculo de Preço-Teto e Margem de Segurança")
            
            opcao_valuation = st.selectbox(
                "Escolha a base de dividendos para precificar a ação:",
                [
                    "Média dos últimos 5 anos", 
                    "Ano Atual (Já Pago + Projeção Restante)", 
                    "Projeções do Próximo Ano"
                ]
            )
            
            media_5_anos = sum(dados_pagos.values()) / len(anos_historicos) if anos_historicos else 0.0
            total_ano_atual = pago_ano_atual + restante_ano_atual
            
            if opcao_valuation == "Média dos últimos 5 anos":
                dividendo_base = media_5_anos
                label_dividendo = "Média (5 anos)"
            elif opcao_valuation == "Ano Atual (Já Pago + Projeção Restante)":
                dividendo_base = total_ano_atual
                label_dividendo = f"Total Projetado ({ano_atual})"
            else:
                dividendo_base = dividendo_ano_seguinte_projetado
                label_dividendo = f"Projetado ({ano_seguinte})"
            
            preco_teto = dividendo_base / yield_desejado
            margem_seguranca = ((preco_teto / preco_atual) - 1) * 100
            
            col1, col2, col3 = st.columns(3)
            col1.metric(f"Div. Base: {label_dividendo}", f"R$ {dividendo_base:.2f}")
            col2.metric("Preço-Teto Máximo", f"R$ {preco_teto:.2f}")
            
            if margem_seguranca > 0:
                col3.metric("Margem de Segurança", f"{margem_seguranca:.1f}%", delta="Descontada (Abaixo do Teto)")
            else:
                col3.metric("Margem de Segurança", f"{margem_seguranca:.1f}%", delta="Cara (Acima do Teto)", delta_color="inverse")
                
    except Exception as e:
        st.error(f"Erro ao processar dados do ticker {ticker_input}. Caso o problema persista, verifique se o ativo digitado está correto. Detalhes: {e}")
