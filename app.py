import streamlit as st
import json
import base64
import os
import re
from datetime import datetime
import PyPDF2
import pandas as pd
import numpy as np
import analisador
from supabase import create_client, Client
from dotenv import load_dotenv

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Nexus Clínico", page_icon="🧬", layout="wide")
# --- ESCONDER MENU DO STREAMLIT ---
st.markdown("""
    <style>
    [data-testid="stHeader"] {visibility: hidden !important;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM A NUVEM ---
load_dotenv(override=True)

@st.cache_resource
def init_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

supabase = init_supabase()

# --- SISTEMA DE AUTENTICAÇÃO E BLOQUEIO ---
if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None

if not st.session_state['usuario_logado']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div style='background: rgba(30, 41, 59, 0.65); padding: 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); box-shadow: 0 10px 30px rgba(0,0,0,0.4);'>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #38bdf8; font-size: 2.8em; margin-bottom: 0;'>🧬 Nexus Clínico</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #94a3b8; font-weight: 400; margin-top: 0;'>Plataforma Comercial SaaS</h3><br>", unsafe_allow_html=True)
        
        tab_login, tab_registro = st.tabs(["🔐 Entrar no Sistema", "📝 Criar Conta de Profissional"])
        
        with tab_login:
            email_login = st.text_input("E-mail Profissional:", key="log_email")
            senha_login = st.text_input("Senha:", type="password", key="log_senha")
            if st.button("Acessar Plataforma", use_container_width=True):
                if not supabase:
                    st.error("Erro Crítico: Falha na conexão. Verifique o arquivo .env.")
                else:
                    try:
                        # Método síncrono padrão. A resposta contém a sessão e o usuário.
                        response = supabase.auth.sign_in_with_password({"email": email_login, "password": senha_login})
                        if response.user:
                            st.session_state['usuario_logado'] = response.user
                            st.rerun()
                        else:
                            st.error("Falha ao validar os dados do usuário.")
                    except Exception as e:
                        # Tratamento simplificado de erros
                        st.error(f"Erro: {str(e)}")

        with tab_registro:
            nome_completo = st.text_input("Nome Completo do Profissional:", key="reg_nome")
            email_novo = st.text_input("E-mail de Trabalho:", key="reg_email")
            senha_nova = st.text_input("Crie uma Senha (mín. 6 dígitos):", type="password", key="reg_senha")
            if st.button("Registrar Nova Clínica / Profissional", use_container_width=True):
                if not supabase:
                    st.error("Erro de conexão com o banco.")
                else:
                    try:
                        # Método síncrono padrão para registro.
                        response = supabase.auth.sign_up({"email": email_novo, "password": senha_nova})
                        if response.user:
                            try:
                                supabase.table("perfis_profissionais").insert({"id": response.user.id, "nome_completo": nome_completo}).execute()
                            except Exception as db_err:
                                pass # Ignora erro de inserção no banco se a tabela não existir, mas o auth foi criado
                            st.success("✅ Conta criada com sucesso! Acesse a aba 'Entrar no Sistema'.")
                    except Exception as e:
                        st.error(f"Erro ao registrar: {str(e)}")
                        
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# CÓDIGO MESTRE: EXECUTA APENAS SE LOGADO
# ==========================================
# (Mantenha o seu código original a partir daqui, começando pela definição da PASTA_BD)

# ==========================================
# CÓDIGO MESTRE: EXECUTA APENAS SE LOGADO
# ==========================================

# --- ISOLAMENTO DO BANCO DE DADOS (MULTI-TENANT) ---
MEDICO_ID = st.session_state['usuario_logado'].id
PASTA_BD = f"banco_pacientes_{MEDICO_ID}"
os.makedirs(PASTA_BD, exist_ok=True)

# --- CABEÇALHO SUPERIOR DE USUÁRIO ---
col_head1, col_head2 = st.columns([4, 1])
with col_head1:
    # Acessa o email com tratamento para atributos do objeto user
    email_logado = getattr(st.session_state['usuario_logado'], 'email', 'Médico Autenticado')
    st.markdown(f"👨‍⚕️ **Profissional Logado:** <span style='color:#38bdf8;'>{email_logado}</span>", unsafe_allow_html=True)
with col_head2:
    if st.button("🚪 Sair da Plataforma", use_container_width=True):
        if supabase: supabase.auth.sign_out()
        st.session_state['usuario_logado'] = None
        st.rerun()
st.markdown("---")

# --- FUNÇÕES DE BANCO DE DADOS ---
def salvar_exame(paciente, data_exame, dados_laudo, biometria=None):
    caminho = os.path.join(PASTA_BD, f"{paciente}.json")
    historico = []
    if os.path.exists(caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            try: historico = json.load(f)
            except json.JSONDecodeError: historico = []
            
    historico = [h for h in historico if h.get('data') != str(data_exame)]
    
    novo_registro = {"data": str(data_exame), "laudo": dados_laudo}
    if biometria: novo_registro["biometria"] = biometria
        
    historico.append(novo_registro)
    historico = sorted(historico, key=lambda x: x.get('data', ''))
    
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=4)

def salvar_biometria_perfil(paciente, biometria):
    caminho = os.path.join(PASTA_BD, f"{paciente}.json")
    if os.path.exists(caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            try: historico = json.load(f)
            except json.JSONDecodeError: historico = []
        if historico:
            historico[-1]["biometria"] = biometria
            with open(caminho, 'w', encoding='utf-8') as f:
                json.dump(historico, f, ensure_ascii=False, indent=4)
            return True
    return False

def ler_biometria(paciente):
    caminho = os.path.join(PASTA_BD, f"{paciente}.json")
    if os.path.exists(caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            try:
                historico = json.load(f)
                if historico and len(historico) > 0 and 'biometria' in historico[-1]:
                    return historico[-1]['biometria']
            except json.JSONDecodeError: pass
    return {"idade": 52, "sexo": "Masculino", "peso": 87.0, "objetivo": "Emagrecimento (Foco Clínico / Síndrome Metabólica)", "atividade": "Moderado (Musculação 3-4x)"}

def extrair_valores_historico(historico):
    dados_grafico = []
    for reg in historico:
        data_ex = reg.get('data')
        if not data_ex: continue
        laudo = reg.get('laudo', {})
        glicose = insulina = hb_glicada = colesterol_total = ldl = hdl = triglicerideos = testosterona = cortisol = tsh = None
        
        for achado in laudo.get('achados', []):
            nome = str(achado.get('marcador', '')).lower()
            valor_str = str(achado.get('valor_encontrado', '')).strip()
            if ',' in valor_str: valor_str = valor_str.replace('.', '').replace(',', '.')
            try:
                match = re.search(r"[-+]?\d*\.\d+|\d+", valor_str)
                if match:
                    val = float(match.group())
                    if 'glicose' in nome or 'glicemia' in nome: glicose = val
                    elif 'insulina' in nome: insulina = val
                    elif 'hemoglobina glicada' in nome or 'hba1c' in nome or 'glicada' in nome: hb_glicada = val
                    elif 'triglicerídeos' in nome or 'triglicerideos' in nome: triglicerideos = val
                    elif 'hdl' in nome: hdl = val
                    elif 'ldl' in nome: ldl = val
                    elif 'colesterol total' in nome or ('colesterol' in nome and 'total' in nome): colesterol_total = val
                    elif 'testosterona' in nome and 'livre' not in nome: testosterona = val
                    elif 'cortisol' in nome: cortisol = val
                    elif 'tsh' in nome: tsh = val
            except: continue
        
        homa_ir = (glicose * insulina) / 405 if glicose is not None and insulina is not None else None
        linha = {"Data": data_ex}
        if glicose is not None: linha["Glicemia"] = glicose
        if hb_glicada is not None: linha["HbA1c"] = hb_glicada
        if homa_ir is not None: linha["HOMA-IR"] = round(homa_ir, 2)
        if colesterol_total is not None: linha["Colesterol Total"] = colesterol_total
        if ldl is not None: linha["LDL"] = ldl
        if hdl is not None: linha["HDL"] = hdl
        if triglicerideos is not None: linha["Triglicerídeos"] = triglicerideos
        if testosterona is not None: linha["Testosterona Total"] = testosterona
        if cortisol is not None: linha["Cortisol"] = cortisol
        if tsh is not None: linha["TSH"] = tsh
        dados_grafico.append(linha)
    return dados_grafico

def extrair_texto_pdf(arquivo_pdf):
    if not arquivo_pdf: return ""
    leitor = PyPDF2.PdfReader(arquivo_pdf)
    texto = ""
    for pagina in leitor.pages: 
        texto += pagina.extract_text() + "\n"
    return texto

def calcular_indices(dados_json):
    glicose = insulina = hdl = triglicerideos = None
    for achado in dados_json.get('achados', []):
        nome = achado.get('marcador', '').lower()
        try:
            val_str = str(achado.get('valor_encontrado', '')).replace(',', '.')
            match = re.search(r"[-+]?\d*\.\d+|\d+", val_str)
            if match:
                val = float(match.group())
                if 'glicose' in nome or 'glicemia' in nome: glicose = val
                elif 'insulina' in nome: insulina = val
                elif 'hdl' in nome: hdl = val
                elif 'triglicerídeos' in nome or 'triglicerideos' in nome: triglicerideos = val
        except: continue
    calculos = {}
    if glicose and insulina:
        homa_ir = (glicose * insulina) / 405
        status_homa = "Resistência à Insulina" if homa_ir >= 2.5 else "HOMA-IR Normal"
        cor_homa = "#dc2626" if homa_ir >= 2.5 else "#16a34a"
        calculos['HOMA-IR'] = f"<p><strong>Índice HOMA-IR:</strong> {homa_ir:.2f} - <span style='color: {cor_homa}; font-weight: bold;'>{status_homa}</span></p>"
    if triglicerideos and hdl:
        relacao = triglicerideos / hdl
        status_rel = "Risco Aterogênico Elevado" if relacao >= 3.5 else "Controlado"
        cor_rel = "#dc2626" if relacao >= 3.5 else "#16a34a"
        calculos['Trig/HDL'] = f"<p><strong>Relação Trig/HDL:</strong> {relacao:.2f} - <span style='color: {cor_rel}; font-weight: bold;'>{status_rel}</span></p>"
    return "".join(calculos.values())

def baixar_html(html_string, nome_arquivo):
    b64 = base64.b64encode(html_string.encode()).decode()
    return f'<br><a href="data:text/html;base64,{b64}" download="{nome_arquivo}.html" class="stButton" style="text-decoration:none; display:inline-block; padding:12px 24px; background:linear-gradient(145deg, #0284c7, #0369a1); color:white; border-radius:10px; font-weight:bold; box-shadow: 4px 4px 10px rgba(0,0,0,0.5);">📥 Baixar Dossiê (HTML)</a>'

def gerar_html_cardapio(paciente, cardapio_md):
    import re
    html_cardapio = cardapio_md.replace('\n', '<br>')
    html_cardapio = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_cardapio)
    html_cardapio = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html_cardapio)
    html_cardapio = re.sub(r'### (.*?)<br>', r'<h3>\1</h3>', html_cardapio)
    html_cardapio = re.sub(r'## (.*?)<br>', r'<h2>\1</h2>', html_cardapio)
    
    html = f"""
    <!DOCTYPE html><html lang="pt-PT"><head><meta charset="UTF-8"><title>Cardápio - {paciente}</title>
    <style>body {{ font-family: 'Segoe UI', sans-serif; color: #333; max-width: 900px; margin: 0 auto; padding: 30px; line-height: 1.6; }}</style>
    </head><body>
    <h1 style="text-align:center;color:#1e3a8a;">Prescrição Dietética Semanal</h1>
    <h3 style="text-align:center;">Paciente: {paciente}</h3>
    <hr>
    <div>{html_cardapio}</div>
    </body></html>
    """
    return html    
def gerar_html_evolucao(paciente, parecer_md):
    html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', parecer_md)
    html_content = re.sub(r'### (.*)', r'<h3>\1</h3>', html_content)
    html_content = re.sub(r'## (.*)', r'<h2>\1</h2>', html_content)
    html_content = re.sub(r'# (.*)', r'<h1>\1</h1>', html_content)
    html_content = html_content.replace('\n', '<br>')
    
    html = f"""
    <!DOCTYPE html><html lang="pt-PT"><head><meta charset="UTF-8"><title>Evolução Clínica - {paciente}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; color: #333; max-width: 900px; margin: 0 auto; padding: 30px; line-height: 1.6; }}
        .header {{ text-align: center; border-bottom: 3px solid #1e3a8a; padding-bottom: 20px; margin-bottom: 30px; }}
        .header h1 {{ color: #1e3a8a; margin: 0 0 5px 0; font-size: 2.2em; }}
        .content {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 25px; border-radius: 8px; white-space: pre-wrap; font-size: 1.05em; }}
        .footer {{ margin-top: 50px; font-size: 0.85em; color: #64748b; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
    </style>
    </head><body>
        <div class="header">
            <h1>Dossiê de Evolução Clínica</h1>
            <h3>Acompanhamento Longitudinal e Avaliação de Progresso</h3>
        </div>
        <p><strong>Paciente:</strong> {paciente}</p>
        <p><strong>Data da Análise:</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
        <div class="content">{html_content}</div>
        <div class="footer">Gerado por Nexus Clínico - Motor de Inteligência Artificial para Alta Performance.</div>
    </body></html>
    """
    return html

def gerar_html_laudo(paciente, data, modulo, dados_json, calculos_html):
    linhas_tabela = ""
    for achado in dados_json.get('achados', []):
        marcador = achado.get('marcador', '')
        resultado = achado.get('valor_encontrado', '')
        referencia = achado.get('valor_referencia', '')
        analise = achado.get('analise_fisiologica', '')
        status = achado.get('status', '').lower()

        if 'otimizado' in status: cor, icone, texto_status = '#16a34a', "🟢", "Otimizado"
        elif 'alerta' in status: cor, icone, texto_status = '#d97706', "🟡", "Alerta Metabólico"
        elif 'risco' in status or 'alterado' in status: cor, icone, texto_status = '#dc2626', "🔴", "Risco Clínico"
        else: cor, icone, texto_status = '#16a34a', ("🟢" if 'normal' in status else "🔸"), status.title()

        valor_formatado = f"<td style='color: {cor}; font-weight:bold;'>{icone} {resultado} <br><span style='font-size: 0.8em; color: {cor};'>{texto_status}</span></td>"
        linhas_tabela += f"<tr><td>{marcador}</td>{valor_formatado}<td>{referencia}</td><td>{analise}</td></tr>"

    html_calculos = f"<h2>🧮 Calculadoras de Risco</h2><div style='background-color: #f8fafc; padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e2e8f0;'>{calculos_html}</div>" if calculos_html else ""

    modulos_avancados = ["Fisiologia do Esporte e Alta Performance", "Performance, Emagrecimento e Endocrinologia", "Painel Completo (Bioquímica + Hematologia)"]
    
    if modulo in modulos_avancados:
        alertas = "".join([f"<li>{a}</li>" for a in dados_json.get('alertas_vermelhos', [])])
        caixa_alertas = f"<div class='alert-box'><ul>{alertas}</ul></div>" if alertas else ""
        alertas_inbody = "".join([f"<li>{a}</li>" for a in dados_json.get('alertas_composicao', [])])
        caixa_inbody = f"<div class='alert-box' style='background-color: #fffbeb; border-color: #f59e0b; color: #b45309;'><strong>⚖️ Alertas de Composição Corporal:</strong><br><ul>{alertas_inbody}</ul></div>" if alertas_inbody else ""
        
        macros = dados_json.get('estrategia_nutricional', {})
        html_macros = ""
        if isinstance(macros, dict) and macros.get('macros'):
            html_macros = f"""
            <div class="insight-box" style="border-left-color: #f59e0b; background-color: #fffbeb;">
                <strong>🍽️ Estratégia de Macronutrientes (Meta):</strong><br>
                Calorias Alvo: {macros.get('calorias_alvo', '')}<br>
                Proteínas: {macros.get('macros', {}).get('proteinas', '')}<br>
                Carboidratos: {macros.get('macros', {}).get('carboidratos', '')}<br>
                Gorduras: {macros.get('macros', {}).get('gorduras', '')}<br>
                <em>Justificativa: {macros.get('justificativa_clinica', '')}</em>
            </div>
            """

        titulo_modulo = "DOSSIÊ CLÍNICO DE ALTA PERFORMANCE" if "Performance" in modulo else "DOSSIÊ CLÍNICO E METABÓLICO"

        html = f"""
        <!DOCTYPE html><html lang="pt-PT"><head><meta charset="UTF-8"><title>Dossiê - {paciente}</title>
        <style>body {{ font-family: 'Segoe UI', sans-serif; color: #333; max-width: 900px; margin: 0 auto; padding: 30px; line-height: 1.6; }} .header {{ text-align: center; border-bottom: 3px solid #1e3a8a; padding-bottom: 20px; margin-bottom: 30px; }} .header h1 {{ color: #1e3a8a; margin: 0 0 5px 0; font-size: 2.2em; }} .alert-box {{ background-color: #fef2f2; border-left: 5px solid #ef4444; padding: 15px; margin-bottom: 20px; }} .eixo-box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 15px; }} .insight-box {{ background-color: #f0fdf4; border-left: 5px solid #22c55e; padding: 15px; margin-bottom: 15px; }} h2 {{ color: #2563eb; font-size: 1.4em; border-bottom: 1px solid #bfdbfe; padding-bottom: 5px; margin-top: 25px; }} table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.95em; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }} th, td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }} th {{ background-color: #1e293b; color: white; }} .footer {{ margin-top: 50px; font-size: 0.85em; color: #64748b; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 20px; }}</style>
        </head><body>
        <div class="header"><h1>{titulo_modulo}</h1><h3>Avaliação Fisiológica Integrada</h3></div>
        <p><strong>Paciente:</strong> {paciente} | <strong>Data:</strong> {data}</p>
        <h2>📊 Resumo Executivo</h2><p>{dados_json.get('resumo_executivo', '')}</p>
        {f"<h2>🚨 Alertas Críticos</h2>{caixa_alertas}" if alertas else ""}
        {caixa_inbody}
        <h2>🧬 Análise Metabólica Cruzada</h2>
        <div class="eixo-box"><strong>Eixo Glicêmico / Captação de Nutrientes:</strong><br>{dados_json.get('eixo_glicemico', '')}</div>
        <div class="eixo-box"><strong>Eixo Hormonal / Anabolismo:</strong><br>{dados_json.get('eixo_hormonal', '')}</div>
        <div class="eixo-box"><strong>Eixo Inflamatório, Lipídico e Dano Muscular:</strong><br>{dados_json.get('eixo_inflamatorio', '')}</div>
        <h2>🎯 Insights para Conduta</h2>
        <div class="insight-box"><strong>Foco Médico / Estratégia Endócrina:</strong><br>{dados_json.get('insight_medico', '')}</div>
        <div class="insight-box"><strong>Foco Nutricional / Suplementação Ergogênica:</strong><br>{dados_json.get('insight_nutricional', '')}</div>
        {html_macros}
        {html_calculos}
        <h2>🔬 Detalhamento (Radar de Marcadores Otimizados)</h2>
        <table><tr><th>Marcador</th><th>Resultado / Status</th><th>Referência do Laboratório</th><th>Análise Fisiológica</th></tr>{linhas_tabela}</table>
        <div class="footer">Gerado por Nexus Clínico - Suporte à Decisão de Alta Performance.</div></body></html>
        """
        return html
    elif modulo == "Microbiologia (Cultura e Antibiograma)":
        bacterias = "".join([f"<li>{b}</li>" for b in dados_json.get('bacterias_isoladas', [])])
        caixa_bacterias = f"<div class='alert-box'><strong>🔬 Microrganismos Isolados:</strong><ul>{bacterias}</ul></div>" if bacterias else "<div class='insight-box'><strong>🔬 Cultura Negativa / Flora Normal</strong></div>"
        
        sensiveis = "<br>".join([f"✅ {s}" for s in dados_json.get('antibioticos_sensiveis', [])])
        resistentes = "<br>".join([f"❌ {r}" for s in dados_json.get('antibioticos_resistentes', [])])
        
        html = f"""
        <!DOCTYPE html><html lang="pt-PT"><head><meta charset="UTF-8"><title>Laudo - {paciente}</title>
        <style>body {{ font-family: 'Segoe UI', sans-serif; color: #333; max-width: 900px; margin: 0 auto; padding: 30px; line-height: 1.6; }} .header {{ text-align: center; border-bottom: 3px solid #1e3a8a; padding-bottom: 20px; margin-bottom: 30px; }} .header h1 {{ color: #1e3a8a; margin: 0 0 5px 0; font-size: 2.2em; }} .alert-box {{ background-color: #fef2f2; border-left: 5px solid #ef4444; padding: 15px; margin-bottom: 20px; }} .eixo-box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 15px; }} .insight-box {{ background-color: #f0fdf4; border-left: 5px solid #22c55e; padding: 15px; margin-bottom: 15px; }} h2 {{ color: #2563eb; font-size: 1.4em; border-bottom: 1px solid #bfdbfe; padding-bottom: 5px; margin-top: 25px; }} table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.95em; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }} th, td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }} th {{ background-color: #1e293b; color: white; }} .footer {{ margin-top: 50px; font-size: 0.85em; color: #64748b; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 20px; }}</style>
        </head><body>
        <div class="header"><h1>LAUDO MICROBIOLÓGICO E INFECCIOSO</h1><h3>Avaliação de Cultura e Antibiograma</h3></div>
        <p><strong>Paciente:</strong> {paciente} | <strong>Data:</strong> {data}</p>
        <h2>📋 Resumo Clínico</h2><p>{dados_json.get('resumo_clinico', '')}</p>
        {caixa_bacterias}
        <h2>💊 Perfil de Sensibilidade Antimicrobiana</h2>
        <div style="display: flex; gap: 20px;">
            <div class="eixo-box" style="flex: 1;"><strong>Antibiograma (Sensível):</strong><br>{sensiveis}</div>
            <div class="eixo-box" style="flex: 1; border-color: #ef4444; background-color: #fef2f2;"><strong>Antibiograma (Resistente):</strong><br>{resistentes}</div>
        </div>
        <h2>🩺 Diretriz Terapêutica</h2>
        <div class="insight-box" style="border-color: #f59e0b; background-color: #fffbeb;"><strong>Conduta Infecciosa:</strong><br>{dados_json.get('conduta_infecciosa', '')}</div>
        <h2>🔬 Detalhamento</h2>
        <table><tr><th>Marcador</th><th>Resultado / Status</th><th>Referência</th><th>Análise Técnica</th></tr>{linhas_tabela}</table>
        <div class="footer">Gerado por Nexus Clínico - Suporte à Decisão Médica.</div></body></html>
        """
        return html
    else:
        html = f"""
        <!DOCTYPE html><html lang="pt-PT"><head><meta charset="UTF-8"><title>Laudo Clínico</title>
        <style>body {{ font-family: sans-serif; color: #333; max-width: 900px; margin: 0 auto; padding: 30px; }} table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }} th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; vertical-align: top; }} th {{ background-color: #1e293b; color: white; }}</style>
        </head><body><h1 style="text-align: center; color: #1e3a8a;">LAUDO CLÍNICO ESPECIALIZADO</h1><p><strong>Paciente:</strong> {paciente} | <strong>Data:</strong> {data} | <strong>Módulo:</strong> {modulo}</p>
        <h3>Resumo Clínico</h3><p>{dados_json.get('resumo_clinico', '')}</p>{html_calculos}
        <h3>Detalhamento (Marcadores)</h3><table><tr><th>Marcador</th><th>Resultado / Status</th><th>Referência Laboratorial</th><th>Análise</th></tr>{linhas_tabela}</table>
        {f"<h3>Radar Científico</h3><p>{dados_json.get('radar_cientifico', '')}</p>" if dados_json.get('radar_cientifico') else ""}
        </body></html>
        """
        return html
       # --- GESTÃO NO MENU LATERAL ---
st.sidebar.title("👥 Gestão de Pacientes")

# BLINDAGEM 1: Ocultar arquivos de cardápio da lista de pacientes
pacientes_salvos = [f.replace('.json', '') for f in os.listdir(PASTA_BD) if f.endswith('.json') and not f.endswith('_cardapio.json')]

opcao_paciente = st.sidebar.radio("Ação:", ["Selecionar Existente", "Novo Paciente"])

paciente_ativo = ""
if opcao_paciente == "Novo Paciente":
    paciente_ativo = st.sidebar.text_input("Nome Completo:")
    if st.sidebar.button("Limpar Tela para Novo"): st.rerun()
else:
    if pacientes_salvos:
        paciente_ativo = st.sidebar.selectbox("Escolha o Paciente:", pacientes_salvos)
    else:
        st.sidebar.warning("Nenhum paciente cadastrado.")

# ZONA DE PERIGO
if paciente_ativo and opcao_paciente == "Selecionar Existente":
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Gestão de Dados")
    with st.sidebar.expander("⚠️ Zona de Perigo"):
        caminho_arquivo = os.path.join(PASTA_BD, f"{paciente_ativo}.json")
        if os.path.exists(caminho_arquivo):
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                try: hist_temp = json.load(f)
                except: hist_temp = []
                
            # BLINDAGEM 2: Só procurar exames se o arquivo for realmente uma lista de histórico
            if isinstance(hist_temp, list) and len(hist_temp) > 0:
                st.markdown("**Apagar um Exame Específico:**")
                datas_exames = [h.get('data') for h in hist_temp if isinstance(h, dict) and h.get('data')]
                
                if datas_exames:
                    data_apagar = st.selectbox("Selecione a data:", datas_exames)
                    if st.button("🗑️ Excluir Exame", key="btn_excluir_exame"):
                        hist_novo = [h for h in hist_temp if isinstance(h, dict) and h.get('data') != data_apagar]
                        with open(caminho_arquivo, 'w', encoding='utf-8') as f: 
                            json.dump(hist_novo, f, ensure_ascii=False, indent=4)
                        st.sidebar.success(f"Exame de {data_apagar} removido do histórico!")
                        st.rerun()
        
        st.markdown("---")
        st.markdown("**Apagar Paciente:**")
        st.caption("Esta ação apagará todo o histórico e laudos deste paciente. Não há como reverter.")
        if st.button("🚨 Excluir Paciente", key="btn_excluir_paciente"):
            # Apaga o exame do paciente
            if os.path.exists(caminho_arquivo): os.remove(caminho_arquivo)
            # Apaga o cardápio do paciente junto
            caminho_cardapio_del = os.path.join(PASTA_BD, f"{paciente_ativo}_cardapio.json")
            if os.path.exists(caminho_cardapio_del): os.remove(caminho_cardapio_del)
            
            st.sidebar.success(f"Paciente {paciente_ativo} excluído!")
            st.rerun()

st.title("🧬 Nexus Clínico | Copiloto Médico")
# --- CONSTRUÇÃO DAS ABAS PRINCIPAIS ---
if not paciente_ativo:
    st.info("👈 Por favor, crie um Novo Paciente ou selecione um existente no menu lateral para iniciar.")
else:
    st.markdown(f"**Paciente Ativo:** `{paciente_ativo}`")
    aba_dashboard, aba_analise, aba_familia, aba_taco, aba_cardapio, aba_microscopia = st.tabs(["📊 Dashboard & Evolução", "🔬 Nova Análise Laboratorial", "👨‍👩‍👧‍👦 Sincronização Familiar", "🍎 Consulta TACO", "🍽️ Prescrição de Cardápio", "🧫 Microscopia Avançada"])

    # ==========================================
    # ABA 1: DASHBOARD
    # ==========================================
    # ==========================================
    # ABA 1: DASHBOARD
    # ==========================================
    with aba_dashboard:
        caminho_arquivo = os.path.join(PASTA_BD, f"{paciente_ativo}.json")
        if os.path.exists(caminho_arquivo):
            with open(caminho_arquivo, 'r', encoding='utf-8') as f: 
                try: hist_paciente = json.load(f)
                except: hist_paciente = []
            
            # --- NOVO BLOCO: PERSISTÊNCIA E EXIBIÇÃO DO ÚLTIMO LAUDO ---
            if hist_paciente:
                ultimo_laudo = hist_paciente[-1]['laudo']
                data_laudo = hist_paciente[-1]['data']
                st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
                st.subheader(f"📄 Último Laudo Gerado: {data_laudo}")
                
                st.markdown("#### 🧬 Análise Metabólica Cruzada")
                colA, colB, colC = st.columns(3)
                with colA: st.info(f"**Eixo Glicêmico:**\n\n{ultimo_laudo.get('eixo_glicemico', '...')}")
                with colB: st.info(f"**Eixo Hormonal:**\n\n{ultimo_laudo.get('eixo_hormonal', '...')}")
                with colC: st.info(f"**Eixo Inflamatório:**\n\n{ultimo_laudo.get('eixo_inflamatorio', '...')}")
                
                st.markdown("#### 🎯 Insights de Conduta")
                st.success(f"**Médica:** {ultimo_laudo.get('insight_medico', '...')}")
                st.success(f"**Nutricional:** {ultimo_laudo.get('insight_nutricional', '...')}")
                st.markdown("</div>", unsafe_allow_html=True)
            # --- FIM DO NOVO BLOCO ---

            st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
            st.subheader("📈 Evolução de Biomarcadores")
            dados_evolucao = extrair_valores_historico(hist_paciente)
            if dados_evolucao and len(dados_evolucao) > 0:
                df = pd.DataFrame(dados_evolucao)
                try: df["Data"] = pd.to_datetime(df["Data"]); df = df.set_index("Data").sort_index()
                except: df = df.set_index("Data")
                
                st.markdown("#### 🩸 Eixo Glicêmico e Resistência à Insulina")
                cg1, cg2, cg3 = st.columns(3)
                with cg1:
                    if "Glicemia" in df.columns: st.markdown("**Glicemia de Jejum**"); st.line_chart(df[["Glicemia"]].dropna(), color="#3b82f6")
                with cg2:
                    if "HbA1c" in df.columns: st.markdown("**HbA1c (%)**"); st.line_chart(df[["HbA1c"]].dropna(), color="#f59e0b")
                with cg3:
                    if "HOMA-IR" in df.columns: st.markdown("**HOMA-IR**"); st.line_chart(df[["HOMA-IR"]].dropna(), color="#dc2626")

                st.markdown("#### 🫀 Perfil Lipídico e Risco Cardiovascular")
                cl1, cl2, cl3, cl4 = st.columns(4)
                with cl1:
                    if "Colesterol Total" in df.columns: st.markdown("**Col. Total**"); st.line_chart(df[["Colesterol Total"]].dropna(), color="#64748b")
                with cl2:
                    if "LDL" in df.columns: st.markdown("**LDL**"); st.line_chart(df[["LDL"]].dropna(), color="#ef4444")
                with cl3:
                    if "HDL" in df.columns: st.markdown("**HDL**"); st.line_chart(df[["HDL"]].dropna(), color="#10b981")
                with cl4:
                    if "Triglicerídeos" in df.columns: st.markdown("**Triglicerídeos**"); st.line_chart(df[["Triglicerídeos"]].dropna(), color="#f97316")

                st.markdown("#### ⚡ Eixo Hormonal (Metabolismo e Catabolismo)")
                ch1, ch2, ch3 = st.columns(3)
                with ch1:
                    if "Testosterona Total" in df.columns: st.markdown("**Testosterona**"); st.line_chart(df[["Testosterona Total"]].dropna(), color="#16a34a")
                with ch2:
                    if "Cortisol" in df.columns: st.markdown("**Cortisol**"); st.line_chart(df[["Cortisol"]].dropna(), color="#8b5cf6")
                with ch3:
                    if "TSH" in df.columns: st.markdown("**TSH**"); st.line_chart(df[["TSH"]].dropna(), color="#d946ef")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if len(hist_paciente) >= 2:
                if st.button("🤖 Gerar Parecer de Evolução Clínica"):
                    with st.spinner("Analisando progressão metabólica através dos 3 Eixos..."):
                        parecer = analisador.gerar_comparativo_evolucao(hist_paciente)
                        st.markdown(f"<div class='caixa-evolucao'>{parecer}</div>", unsafe_allow_html=True)
                        
                        html_evolucao = gerar_html_evolucao(paciente_ativo, parecer)
                        nome_arquivo_evo = f"Evolucao_{paciente_ativo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
                        st.markdown(baixar_html(html_evolucao, nome_arquivo_evo), unsafe_allow_html=True)
            
            with st.expander("Ver histórico bruto"): st.json(hist_paciente)
        else: st.info("O paciente ainda não possui exames salvos nesta clínica.")

    # ==========================================
    # ABA 2: NOVA ANÁLISE
    # ==========================================
    with aba_analise:
        st.markdown("### 👤 Perfil Biométrico e Objetivo")
        
        bio = ler_biometria(paciente_ativo)
        
        lista_sexo = ["Masculino", "Feminino"]
        idx_sexo = lista_sexo.index(bio.get('sexo', "Masculino")) if bio.get('sexo', "Masculino") in lista_sexo else 0
        
        lista_obj = [
            "Emagrecimento (Foco Clínico / Síndrome Metabólica)", 
            "Manutenção / Saúde Geral", 
            "Hipertrofia Estrita (Ganho de Massa Magra)", 
            "Performance Atlética de Elite"
        ]
        idx_obj = lista_obj.index(bio.get('objetivo', lista_obj[0])) if bio.get('objetivo', lista_obj[0]) in lista_obj else 0
        
        lista_ativ = ["Sedentário", "Leve (1-2x sem)", "Moderado (Musculação 3-4x)", "Intenso (Musculação 5-6x)", "Atleta de Elite"]
        idx_ativ = lista_ativ.index(bio.get('atividade', lista_ativ[2])) if bio.get('atividade', lista_ativ[2]) in lista_ativ else 2

        st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        
        with col_b1: idade_paciente = st.number_input("Idade:", min_value=0, max_value=120, value=int(bio.get('idade', 52)), step=1, key=f"id_{paciente_ativo}")
        with col_b2: sexo_paciente = st.selectbox("Sexo:", lista_sexo, index=idx_sexo, key=f"sx_{paciente_ativo}")
        with col_b3: peso_paciente = st.number_input("Peso Atual (kg):", min_value=30.0, max_value=250.0, value=float(bio.get('peso', 87.0)), step=0.1, key=f"ps_{paciente_ativo}")
        with col_b4: objetivo = st.selectbox("Objetivo Clínico/Esportivo:", lista_obj, index=idx_obj, key=f"ob_{paciente_ativo}")

        col_t1, col_t2 = st.columns(2)
        with col_t1: atividade_fisica = st.selectbox("Treino/Atividade:", lista_ativ, index=idx_ativ, key=f"at_{paciente_ativo}")
        with col_t2: modulo_selecionado = st.selectbox("Módulo Clínico de Análise:", [
                "Fisiologia do Esporte e Alta Performance",
                "Performance, Emagrecimento e Endocrinologia",
                "Microbiologia (Cultura e Antibiograma)",
                "Painel Completo (Bioquímica + Hematologia)",
                "Imunologia (Sorologias Básicas)",
                "Imunologia - Autoimunidade",
                "Imunologia - Alergias (IgE Específicas)",
                "Imunologia - Marcadores Tumorais",
                "Imunologia - Toxoplasmose",
                "Imunologia - COVID-19"
            ])
            # --- NOVO: CAMPO DO CICLO MENSTRUAL E DUM ---
        ciclo_menstrual = ""
        dum = ""
        if sexo_paciente == "Feminino":
            col_fem1, col_fem2 = st.columns(2)
            with col_fem1:
                ciclo_menstrual = st.selectbox("Fase do Ciclo Menstrual:", ["Não Aplicável / Menopausa / Anticoncepcional", "Fase Folicular", "Fase Ovulatória", "Fase Lútea"], key=f"ciclo_{paciente_ativo}")
            with col_fem2:
                if ciclo_menstrual != "Não Aplicável / Menopausa / Anticoncepcional":
                    dum = st.text_input("Data da Última Menstruação (DUM):", placeholder="Ex: 12/05/2026 ou 'Não lembra'", key=f"dum_{paciente_ativo}")
        # --------------------------------------
        
        if st.button("💾 Salvar Perfil (Sem Exame)", key=f"btn_salvar_bio_{paciente_ativo}"):
            bio_nova = {"idade": idade_paciente, "sexo": sexo_paciente, "peso": peso_paciente, "objetivo": objetivo, "atividade": atividade_fisica}
            sucesso = salvar_biometria_perfil(paciente_ativo, bio_nova)
            if sucesso:
                st.success("✅ Perfil biométrico atualizado com sucesso!")
            else:
                st.warning("⚠️ O paciente precisa ter pelo menos um exame salvo para gravar a biometria pela primeira vez.")

        contexto = st.text_area("Variáveis de Contexto:", placeholder="Ex: Uso de medicamentos, sintomas, rotina alimentar...")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("### 📄 Importação de Exames (Único ou em Lote)")
        
        uploaded_sangues = st.file_uploader("Exames de Sangue / Culturas (Pode selecionar vários)", type="pdf", accept_multiple_files=True)
        
        dict_datas = {}
        if uploaded_sangues:
            st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
            st.markdown("#### Defina as datas para os exames importados:")
            for idx, arquivo in enumerate(uploaded_sangues):
                col_d1, col_d2 = st.columns([3, 1])
                with col_d1: st.write(f"📄 {arquivo.name}")
                with col_d2: dict_datas[arquivo.name] = st.date_input("Data do Exame:", key=f"data_{arquivo.name}_{idx}_{paciente_ativo}")
            st.markdown("</div>", unsafe_allow_html=True)

        uploaded_inbody = st.file_uploader("⚖️ InBody ou DEXA (Opcional - Relativo ao exame mais recente)", type="pdf")

        if uploaded_sangues and st.button("🚀 Processar Exames e Gerar Inteligência"):
            
            laudo_mais_recente = None
            data_mais_recente = None
            
            biometria_atual = {
                "idade": idade_paciente,
                "sexo": sexo_paciente,
                "peso": peso_paciente,
                "objetivo": objetivo,
                "atividade": atividade_fisica
            }
            
            progress_text = "A extrair dados e a comunicar com a Inteligência Executiva. Por favor, aguarde."
            my_bar = st.progress(0, text=progress_text)
            
            total_arquivos = len(uploaded_sangues)
            for idx, arquivo in enumerate(uploaded_sangues):
                percentual = int(((idx) / total_arquivos) * 100)
                my_bar.progress(percentual, text=f"Processando arquivo {idx+1} de {total_arquivos}: {arquivo.name}")
                
                texto_sangue = extrair_texto_pdf(arquivo)
                texto_inbody = ""
                if idx == (total_arquivos - 1) and uploaded_inbody:
                    texto_inbody = extrair_texto_pdf(uploaded_inbody)
                    
                texto_completo = texto_sangue + ("\n\n--- DADOS DE BIOIMPEDÂNCIA ---\n" + texto_inbody if texto_inbody else "")
                # --- NOVO: CONTEXTO COM CICLO MENSTRUAL ---
                contexto_completo = f"Idade: {idade_paciente} anos\nSexo: {sexo_paciente}\n"
                if ciclo_menstrual:
                    contexto_completo += f"Fase do Ciclo Menstrual: {ciclo_menstrual}\n"
                contexto_completo += f"Peso Atual: {peso_paciente} kg\nObjetivo Principal: {objetivo}\nNível de Treino: {atividade_fisica}\nInformações Adicionais: {contexto}"
                
                try:
                    with open('diretrizes_essenciais.txt', 'r', encoding='utf-8') as f: diretrizes = f.read()
                except FileNotFoundError: diretrizes = "Avalie buscando padrões subclínicos."
                
                resposta_ia = analisador.gerar_laudo_clinico(texto_completo, diretrizes, contexto_completo, modulo_selecionado)
                
                try:
                    dados_laudo = json.loads(resposta_ia)
                    if "erro" in dados_laudo: 
                        st.error(f"Erro no ficheiro {arquivo.name}: {dados_laudo['erro']}")
                    else:
                        data_deste_exame = dict_datas[arquivo.name]
                        salvar_exame(paciente_ativo, data_deste_exame, dados_laudo, biometria_atual)
                        st.success(f"✅ Exame ({data_deste_exame}) processado e arquivado com sucesso.")
                        laudo_mais_recente = dados_laudo
                        data_mais_recente = data_deste_exame
                except Exception as e: 
                    st.error(f"Erro na geração JSON do ficheiro {arquivo.name}.")
                    
            my_bar.progress(100, text="Processamento concluído!")
            
            if laudo_mais_recente:
                html_calculadoras = calcular_indices(laudo_mais_recente)
                if html_calculadoras: st.markdown(html_calculadoras, unsafe_allow_html=True)
                
                modulos_avancados = ["Fisiologia do Esporte e Alta Performance", "Performance, Emagrecimento e Endocrinologia", "Painel Completo (Bioquímica + Hematologia)"]
                if modulo_selecionado in modulos_avancados:
                    st.subheader("📊 Resumo Executivo")
                    st.info(laudo_mais_recente.get('resumo_executivo', ''))
                    if laudo_mais_recente.get('alertas_vermelhos'): st.markdown("<div class='alerta-vermelho'><strong>🚨 Alertas Críticos:</strong><br>" + "<br>".join([f"• {a}" for a in laudo_mais_recente.get('alertas_vermelhos')]) + "</div>", unsafe_allow_html=True)
                    if laudo_mais_recente.get('alertas_composicao'): st.markdown("<div class='alerta-amarelo'><strong>⚖️ Alertas de Composição Corporal (InBody/DEXA):</strong><br>" + "<br>".join([f"• {a}" for a in laudo_mais_recente.get('alertas_composicao')]) + "</div>", unsafe_allow_html=True)
                    
                    st.subheader("🧬 Análise Metabólica Cruzada")
                    cc1, cc2, cc3 = st.columns(3)
                    with cc1: st.markdown("**Eixo Glicêmico:**"); st.write(laudo_mais_recente.get('eixo_glicemico', ''))
                    with cc2: st.markdown("**Eixo Hormonal:**"); st.write(laudo_mais_recente.get('eixo_hormonal', ''))
                    with cc3: st.markdown("**Eixo Inflamatório:**"); st.write(laudo_mais_recente.get('eixo_inflamatorio', ''))
                        
                    st.subheader("🎯 Insights para Conduta")
                    st.success(f"**Estratégia Clínica:**\n{laudo_mais_recente.get('insight_medico', '')}")
                    
                    macros = laudo_mais_recente.get('estrategia_nutricional', {})
                    if macros:
                        st.info(f"**🔥 Alvo Calórico e Macros:**\nCalorias: {macros.get('calorias_alvo', '')} | Proteínas: {macros.get('macros', {}).get('proteinas', '')} | Carboidratos: {macros.get('macros', {}).get('carboidratos', '')} | Gorduras: {macros.get('macros', {}).get('gorduras', '')}")
                
                elif modulo_selecionado == "Microbiologia (Cultura e Antibiograma)":
                    st.subheader("🦠 Análise Microbiológica e Infecciosa")
                    st.info(laudo_mais_recente.get('resumo_clinico', ''))
                    
                    bacterias = laudo_mais_recente.get('bacterias_isoladas', [])
                    if bacterias: st.markdown("<div class='alerta-vermelho'><strong>🔬 Microrganismos Isolados:</strong><br>" + "<br>".join([f"• {b}" for b in bacterias]) + "</div>", unsafe_allow_html=True)
                    else: st.success("✅ Cultura Negativa / Flora Normal.")
                    
                    col_mic1, col_mic2 = st.columns(2)
                    with col_mic1:
                        sensiveis = laudo_mais_recente.get('antibioticos_sensiveis', [])
                        if sensiveis: st.markdown("**✅ Antibiograma (Sensível):**\n" + "\n".join([f"- {s}" for s in sensiveis]))
                    with col_mic2:
                        resistentes = laudo_mais_recente.get('antibioticos_resistentes', [])
                        if resistentes: st.markdown("**🚨 Antibiograma (Resistente):**\n" + "\n".join([f"- {r}" for r in resistentes]))
                        
                    st.subheader("💊 Diretriz Terapêutica")
                    st.warning(f"**Conduta Infecciosa:**\n{laudo_mais_recente.get('conduta_infecciosa', 'N/A')}")
                
                else:
                    st.subheader("📋 Resumo Clínico")
                    st.write(laudo_mais_recente.get('resumo_clinico', 'Não gerado.'))
                    if laudo_mais_recente.get('radar_cientifico'): st.info(f"🔬 **Radar Científico:**\n{laudo_mais_recente.get('radar_cientifico')}")
                
                nome_arquivo_laudo = f"Laudo_{paciente_ativo.replace(' ', '_')}_{data_mais_recente}"
                html_final_laudo = gerar_html_laudo(paciente_ativo, data_mais_recente, modulo_selecionado, laudo_mais_recente, html_calculadoras)
                st.markdown(baixar_html(html_final_laudo, nome_arquivo_laudo), unsafe_allow_html=True)

    # ==========================================
    # ABA 3: SINCRONIZAÇÃO FAMILIAR
    # ==========================================
    with aba_familia:
        st.markdown("### 🤝 Alinhamento Metabólico de Casal / Família")
        st.info("Selecione dois pacientes já analisados no sistema para cruzar seus dossiês e gerar uma rotina unificada.")
        
        st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
        col_f1, col_f2 = st.columns(2)
        with col_f1: paciente_1 = st.selectbox("Paciente 1 (Base):", ["Selecione..."] + pacientes_salvos, key="p1")
        with col_f2: paciente_2 = st.selectbox("Paciente 2 (Sincronizar com):", ["Selecione..."] + pacientes_salvos, key="p2")
        
        if paciente_1 != "Selecione..." and paciente_2 != "Selecione...":
            if paciente_1 == paciente_2:
                st.warning("⚠️ Selecione dois pacientes diferentes.")
            else:
                if st.button("🔄 Gerar Planejamento Sincronizado", use_container_width=True):
                    with st.spinner("Cruzando vias metabólicas..."):
                        with open(os.path.join(PASTA_BD, f"{paciente_1}.json"), 'r', encoding='utf-8') as f: 
                            try: hist_p1 = json.load(f)
                            except: hist_p1 = []
                        with open(os.path.join(PASTA_BD, f"{paciente_2}.json"), 'r', encoding='utf-8') as f: 
                            try: hist_p2 = json.load(f)
                            except: hist_p2 = []
                        if not hist_p1 or not hist_p2: st.error("Ambos precisam ter histórico.")
                        else:
                            resultado_sync = analisador.gerar_sincronizacao_familiar(paciente_1, hist_p1, paciente_2, hist_p2)
                            try:
                                dados_sync = json.loads(resultado_sync)
                                if "erro" in dados_sync: st.error(dados_sync["erro"])
                                else:
                                    st.success("Sincronização concluída!")
                                    st.markdown(f"**🔬 Análise Conjunta:** {dados_sync.get('analise_conjunta', '')}")
                                    st.markdown("---")
                                    col_lista1, col_lista2 = st.columns([1, 2])
                                    with col_lista1:
                                        st.write("🛒 **Lista Essencial:**")
                                        for item in dados_sync.get('lista_compras_base', []): st.markdown(f"- {item}")
                                    with col_lista2:
                                        st.subheader("🍽️ Refeições (Porções Individuais)")
                                        for ref in dados_sync.get('refeicoes_sincronizadas', []):
                                            with st.expander(f"🔹 {ref.get('refeicao', '')} — Base: {ref.get('base_alimentar', '')}"):
                                                r1, r2 = st.columns(2)
                                                with r1: st.markdown(f"**{paciente_1}:**<br>{ref.get('porcao_p1', '')}", unsafe_allow_html=True)
                                                with r2: st.markdown(f"**{paciente_2}:**<br>{ref.get('porcao_p2', '')}", unsafe_allow_html=True)
                                    st.info(f"💡 **Dica (Meal Prep):** {dados_sync.get('dica_preparo', '')}")
                            except: st.error("Erro interno de formatação.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================
    # ABA 4: CONSULTA TACO
    # ==========================================
    with aba_taco:
        st.markdown("### 🍎 Tabela TACO - Inteligência Nutricional")
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_taco = os.path.join(diretorio_atual, "taco.csv")
        
        st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
        if os.path.exists(caminho_taco):
            tentativas = [
                {"sep": ",", "encoding": "utf-8", "skiprows": 0},
                {"sep": ";", "encoding": "utf-8", "skiprows": 0},
                {"sep": ",", "encoding": "latin-1", "skiprows": 0},
                {"sep": ";", "encoding": "latin-1", "skiprows": 0},
                {"sep": ",", "encoding": "utf-8", "skiprows": 2},
                {"sep": ";", "encoding": "utf-8", "skiprows": 2},
                {"sep": ",", "encoding": "latin-1", "skiprows": 2},
                {"sep": ";", "encoding": "latin-1", "skiprows": 2}
            ]
            
            melhor_df = pd.DataFrame()
            max_cols = 0
            for config in tentativas:
                try:
                    temp_df = pd.read_csv(caminho_taco, sep=config["sep"], encoding=config["encoding"], skiprows=config["skiprows"], on_bad_lines='skip')
                    if len(temp_df.columns) > max_cols:
                        max_cols = len(temp_df.columns)
                        melhor_df = temp_df
                except: continue
                
            df_taco = melhor_df
            
            if not df_taco.empty:
                df_taco = df_taco.dropna(axis=1, how='all')
                busca_alimento = st.text_input("🔍 Procure o alimento (ex: frango, leite, arroz):")
                
                if busca_alimento:
                    busca_lower = busca_alimento.lower()
                    mask = np.column_stack([df_taco[col].astype(str).str.lower().str.contains(busca_lower, na=False) for col in df_taco.columns])
                    resultado = df_taco.loc[mask.any(axis=1)]
                    if not resultado.empty: st.dataframe(resultado, use_container_width=True)
                    else: st.warning("Alimento não encontrado.")
                else:
                    st.dataframe(df_taco.head(50), use_container_width=True)
            else:
                st.error("O ficheiro existe, mas está corrompido.")
        else:
            st.error(f"⚠️ O ficheiro 'taco.csv' não foi encontrado na pasta do sistema.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================
    # ABA 5: PRESCRIÇÃO DE CARDÁPIO
    # ==========================================
    with aba_cardapio:
        caminho_arquivo = os.path.join(PASTA_BD, f"{paciente_ativo}.json")
        if not os.path.exists(caminho_arquivo):
            st.warning("É necessário gerar o Laudo do paciente na Aba 'Nova Análise' antes de prescrever um cardápio.")
        else:
            with open(caminho_arquivo, 'r', encoding='utf-8') as f: 
                try: hist_paciente = json.load(f)
                except: hist_paciente = []
                
            if not hist_paciente:
                st.warning("Histórico vazio. Gere um laudo primeiro.")
            else:
                laudo_recente = hist_paciente[-1].get('laudo', {})
                alertas = laudo_recente.get('alertas_vermelhos', []) + laudo_recente.get('alertas_composicao', [])
                macros = laudo_recente.get('estrategia_nutricional', {})
                
                st.markdown("### 🧠 Painel de Decisão Clínica Compartilhada")
                sugestao_dieta_ia = "Padrão / Reeducação Alimentar"
                for alerta in alertas:
                    alerta_lower = str(alerta).lower()
                    if "insulina" in alerta_lower or "glicada" in alerta_lower or "homa" in alerta_lower or "glicemia" in alerta_lower:
                        sugestao_dieta_ia = "Low Carb (Foco Sensibilidade à Insulina) ou Dieta Mediterrânea"
                        break
                    elif "triglicer" in alerta_lower or "colesterol" in alerta_lower or "ldl" in alerta_lower:
                        sugestao_dieta_ia = "Dieta Mediterrânea (Foco Anti-inflamatório / Controle Lipídico)"
                        break

                st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
                col_dec1, col_dec2 = st.columns([1, 1])
                with col_dec1:
                    st.markdown("#### 🚨 Condições Clínicas Detetadas:")
                    if alertas:
                        for alerta in alertas: st.markdown(f"- <span style='color:#fca5a5;'>{alerta}</span>", unsafe_allow_html=True)
                    else: st.success("✅ Nenhum marcador de risco crítico detetado.")
                    st.info(f"💡 **Recomendação da IA:** Sugere-se a adoção da linha **{sugestao_dieta_ia}**.")
                
                with col_dec2:
                    st.markdown("#### 🎯 Alvo Macronutricional Ativo:")
                    if isinstance(macros, dict) and macros.get('macros'):
                        st.write(f"**Calorias Totais:** {macros.get('calorias_alvo', 'N/A')}")
                        st.write(f"**Proteínas:** {macros.get('macros', {}).get('proteinas', 'N/A')}")
                        st.write(f"**Carboidratos:** {macros.get('macros', {}).get('carboidratos', 'N/A')}")
                        st.write(f"**Gorduras:** {macros.get('macros', {}).get('gorduras', 'N/A')}")
                        st.caption(f"*Justificativa:* {macros.get('justificativa_clinica', '')}")
                    else: st.warning("Estratégia de macros não encontrada no último laudo.")
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("### 📋 Configuração da Dieta Semanal")
                st.markdown("<div class='caixa-evolucao'>", unsafe_allow_html=True)
                col_cfg1, col_cfg2 = st.columns(2)
                with col_cfg1:
                    estrategia_escolhida = st.selectbox("Linha Dietética a Aplicar (Validação):", [
                        "Padrão / Reeducação Alimentar",
                        "Dieta Mediterrânea (Foco Anti-inflamatório/Lipídios)",
                        "Low Carb (Foco Sensibilidade à Insulina)",
                        "Ciclo de Carboidratos (Foco Alta Performance/Hipertrofia)",
                        "Plant-Based / Vegetariana"
                    ])
                with col_cfg2:
                    restricoes = st.text_input("Restrições e Preferências:", placeholder="Ex: Alérgico a castanhas, treina às 19h...")
                    
                # --- NOVO: PERSISTÊNCIA E DOWNLOAD DO CARDÁPIO ---
                caminho_cardapio = os.path.join(PASTA_BD, f"{paciente_ativo}_cardapio.json")
                
                if st.button("🍽️ Gerar Cardápio Semanal Sob Medida", use_container_width=True):
                    with st.spinner("Construindo as refeições..."):
                        cardapio_gerado = analisador.gerar_cardapio_semanal(paciente_ativo, laudo_recente, estrategia_escolhida, restricoes)
                        
                        # Salvar cardapio para não perder no F5
                        with open(caminho_cardapio, 'w', encoding='utf-8') as fc:
                            json.dump({"cardapio": cardapio_gerado}, fc, ensure_ascii=False)
                            
                        st.rerun() # Atualiza a página para exibir o cardápio salvo
                
                # Exibir cardápio persistido na tela
                if os.path.exists(caminho_cardapio):
                    with open(caminho_cardapio, 'r', encoding='utf-8') as fc:
                        dados_c = json.load(fc)
                        cardapio_gerado = dados_c.get("cardapio", "")
                        
                    if cardapio_gerado:
                        st.success("Último Cardápio formulado carregado com sucesso!")
                        
                        # Botão de Download HTML
                        html_c = gerar_html_cardapio(paciente_ativo, cardapio_gerado)
                        st.markdown(baixar_html(html_c, f"Cardapio_{paciente_ativo}"), unsafe_allow_html=True)
                        
                        st.markdown("<div style='background: rgba(15, 23, 42, 0.5); padding:20px; border-radius:10px;'>", unsafe_allow_html=True)
                        st.markdown(cardapio_gerado)
                        st.markdown("</div>", unsafe_allow_html=True)
                # ---------------------------------------------------

    # ==========================================
    # ABA 6: MICROSCOPIA E VISÃO COMPUTACIONAL
    # ==========================================
    with aba_microscopia:
        st.markdown("### 🧫 Visão Computacional para Lâminas de Microscópio")
        st.info("Faça o upload de uma fotografia da lâmina do microscópio para realizar a varredura.")
        
        col_m1, col_m2 = st.columns([1, 2])
        
        with col_m1:
            st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
            tipo_lamina = st.selectbox("Foco da Análise Laboratorial:", [
                "Esfregaço Sanguíneo (Série Vermelha e Branca)",
                "Microbiologia (Coloração de Gram / Ziehl-Neelsen)",
                "Sedimentoscopia de Urina (EAS)",
                "Parasitologia / Fezes",
                "Morfologia Celular Geral"
            ])
            contexto_lamina = st.text_area("Contexto Clínico ou Suspeita:", placeholder="Ex: Suspeita de anemia...")
            imagem_lamina = st.file_uploader("Upload da Lâmina (JPG/PNG)", type=["jpg", "jpeg", "png"])
            
            if imagem_lamina:
                st.image(imagem_lamina, caption="Lâmina Carregada", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
                
        with col_m2:
            st.markdown("<div class='painel-decisao'>", unsafe_allow_html=True)
            if imagem_lamina and st.button("🔍 Iniciar Varredura Morfológica", use_container_width=True):
                with st.spinner("A rede neural está a varrer a morfologia e os padrões de coloração..."):
                    img_bytes = imagem_lamina.getvalue()
                    resultado_lamina = analisador.analisar_lamina_microscopia(img_bytes, contexto_lamina, tipo_lamina)
                    
                    try:
                        dados_lamina = json.loads(resultado_lamina)
                        if "erro" in dados_lamina:
                            st.error(dados_lamina["erro"])
                        else:
                            st.success("✅ Varredura Morfológica Concluída!")
                            
                            st.markdown("#### 🔬 Achados Estruturais na Lâmina")
                            for achado in dados_lamina.get("achados_morfologicos", []):
                                st.markdown(f"**• {achado.get('estrutura', 'Estrutura')}:** {achado.get('descricao', '')}")
                            
                            st.markdown("---")
                            st.markdown(f"**🧫 Qualidade da Amostra:** {dados_lamina.get('qualidade_amostra', 'N/A')}")
                            st.info(f"**🩺 Hipótese Diagnóstica de Bancada:** {dados_lamina.get('hipotese_diagnostica', 'N/A')}")
                            
                            alertas = dados_lamina.get("alertas", [])
                            if alertas:
                                st.markdown("<div class='alerta-vermelho'><strong>🚨 Alertas Morfológicos Identificados:</strong><br>" + "<br>".join([f"• {a}" for a in alertas]) + "</div>", unsafe_allow_html=True)
                            else:
                                st.success("Nenhuma atipia crítica ou alerta morfológico grave identificado.")
                                
                            data_atual = datetime.now().strftime('%d/%m/%Y')
                            linhas_achados = "".join([f"<li><strong>{a.get('estrutura', '')}:</strong> {a.get('descricao', '')}</li>" for a in dados_lamina.get("achados_morfologicos", [])])
                            alertas_html = f"<div style='background-color: #fef2f2; border-left: 5px solid #ef4444; padding: 15px; margin-bottom: 20px; color: #b91c1c;'><strong>🚨 Alertas Morfológicos:</strong><ul>{''.join([f'<li>{a}</li>' for a in alertas])}</ul></div>" if alertas else ""
                                
                            html_microscopia = f"""
                            <!DOCTYPE html><html lang="pt-PT"><head><meta charset="UTF-8"><title>Laudo de Microscopia - {paciente_ativo}</title>
                            <style>body {{ font-family: 'Segoe UI', sans-serif; color: #333; max-width: 900px; margin: 0 auto; padding: 30px; line-height: 1.6; }} .header {{ text-align: center; border-bottom: 3px solid #1e3a8a; padding-bottom: 20px; margin-bottom: 30px; }} .header h1 {{ color: #1e3a8a; margin: 0 0 5px 0; font-size: 2.2em; }} .box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px; margin-bottom: 20px; }} h2 {{ color: #2563eb; font-size: 1.4em; border-bottom: 1px solid #bfdbfe; padding-bottom: 5px; margin-top: 25px; }} ul {{ padding-left: 20px; }} li {{ margin-bottom: 8px; }} .footer {{ margin-top: 50px; font-size: 0.85em; color: #64748b; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 20px; }}</style>
                            </head><body><div class="header"><h1>LAUDO DE MICROSCOPIA DIGITAL</h1><h3>Análise Morfológica Assistida por IA</h3></div>
                            <p><strong>Paciente:</strong> {paciente_ativo} | <strong>Data da Análise:</strong> {data_atual}</p><p><strong>Foco da Análise:</strong> {tipo_lamina}</p><p><strong>Contexto Clínico:</strong> {contexto_lamina}</p>
                            {alertas_html}<h2>🔬 Achados Estruturais</h2><div class="box"><ul>{linhas_achados}</ul></div>
                            <h2>🧫 Qualidade da Amostra</h2><p>{dados_lamina.get('qualidade_amostra', 'N/A')}</p>
                            <h2>🩺 Hipótese Diagnóstica</h2><div class="box" style="background-color: #f0fdf4; border-color: #22c55e;"><p><strong>Conclusão de Bancada:</strong> {dados_lamina.get('hipotese_diagnostica', 'N/A')}</p></div>
                            <div class="footer">Gerado por Nexus Clínico - Visão Computacional para Biomedicina.</div></body></html>
                            """
                            nome_arquivo_micro = f"Microscopia_{paciente_ativo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
                            st.markdown(baixar_html(html_microscopia, nome_arquivo_micro), unsafe_allow_html=True)
                                
                    except json.JSONDecodeError: st.error("Erro: A IA não retornou o formato estruturado correto.")
            else:
                st.markdown("#### Resultados da Varredura")
                st.write("Aguardando upload da fotografia e o comando para iniciar a varredura neural...")
            st.markdown("</div>", unsafe_allow_html=True)
