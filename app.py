import streamlit as st
import os
import io
import time
import json
import base64
import tempfile
import urllib.request
from datetime import datetime
from PIL import Image
import PyPDF2
from supabase import create_client, Client
from fpdf import FPDF
import anthropic
from streamlit_drawable_canvas import st_canvas

# ================= 1. CONFIGURAÇÕES E CHAVES =================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://xhkekpyokrcvhgepatmc.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable__lopYakoLGVj7-uFY25r4A_9Hzs-2nN")
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

# Configuração estável
st.set_page_config(
    page_title="Nexus Estética AI", 
    layout="wide", 
    page_icon="✨",
    initial_sidebar_state="expanded"
)

if "supabase_client" not in st.session_state:
    st.session_state.supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = st.session_state.supabase_client

# ================= MAPA REGULATÓRIO MULTI-CONSELHO =================
MAPA_CONSELHOS = {
    "CRBM": {
        "orgao": "Conselho Federal de Biomedicina (CFBM)",
        "resolucoes": "Resoluções CFBM nº 241/2014 (atos do biomédico em estética) e nº 359/2023 (tricologia e complementos)",
        "limites": "Procedimentos injetáveis, bioestimulação, fios e tecnologias dentro da habilitação em Biomedicina Estética.",
        "termo_profissional": "Biomédico(a) Esteta"
    },
    "CRO": {
        "orgao": "Conselho Federal de Odontologia (CFO)",
        "resolucoes": "Resolução CFO nº 198/2019 (reconhecimento da Harmonização Orofacial como especialidade)",
        "limites": "Região anatômica de cabeça e pescoço, a partir de linha que tangencia o osso hióide até o terço superior facial, com finalidade funcional e estética.",
        "termo_profissional": "Cirurgião(ã)-Dentista / Especialista em HOF"
    },
    "CRM": {
        "orgao": "Conselho Federal de Medicina (CFM)",
        "resolucoes": "Resolução CFM nº 2.336/2023 e pareceres técnicos da SBD e SBCP",
        "limites": "Diagnóstico nosológico, prescrição médica integral e execução de procedimentos invasivos faciais e corporais.",
        "termo_profissional": "Médico(a)"
    },
    "COREN": {
        "orgao": "Conselho Federal de Enfermagem (COFEN)",
        "resolucoes": "Resoluções COFEN nº 529/2016 e nº 626/2020",
        "limites": "Consulta de enfermagem estética, avaliação tecidual e administração de substâncias autorizadas por pós-graduação lato sensu.",
        "termo_profissional": "Enfermeiro(a) Esteta"
    },
    "CRF": {
        "orgao": "Conselho Federal de Farmácia (CFF)",
        "resolucoes": "Resoluções CFF nº 616/2015 e nº 645/2017",
        "limites": "Saúde estética e responsabilidade técnica em procedimentos injetáveis não cirúrgicos pelo farmacêutico habilitado.",
        "termo_profissional": "Farmacêutico(a) Esteta"
    }
}

# ================= 2. ESTÉTICA VISUAL (CSS LIMPO E SEM BLOQUEIOS) =================
st.markdown("""
    <style>
    .stButton>button {
        background-color: #C5A880 !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        min-height: 48px !important;
        font-weight: bold !important;
        font-size: 15px !important;
        transition: all 0.3s ease-in-out !important;
    }
    .stButton>button:hover {
        background-color: #A4865D !important;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.1) !important;
    }
    h1, h2, h3 { color: #2C3E50; font-family: 'Georgia', serif; }
    [data-testid="stSidebar"] { background-color: #FAF8F5; }
    </style>
""", unsafe_allow_html=True)

# Gestão de Sessão Persistente
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "perfil_profissional" not in st.session_state:
    st.session_state.perfil_profissional = None
if "laudo_ativo" not in st.session_state:
    st.session_state.laudo_ativo = None
if "pdf_plano_bytes" not in st.session_state:
    st.session_state.pdf_plano_bytes = None
if "pdf_tcle_bytes" not in st.session_state:
    st.session_state.pdf_tcle_bytes = None
if "paciente_atendido" not in st.session_state:
    st.session_state.paciente_atendido = ""
if "ultimo_pront_id" not in st.session_state:
    st.session_state.ultimo_pront_id = None
if "ultimo_pac_id" not in st.session_state:
    st.session_state.ultimo_pac_id = None
if "exibir_formulario_mobile" not in st.session_state:
    st.session_state.exibir_formulario_mobile = True

# Auto-reconectar via Parâmetro de URL após F5
if not st.session_state.usuario_logado and "user_id" in st.query_params:
    saved_id = st.query_params["user_id"]
    try:
        perfil_auto = supabase.table("profissionais").select("*").eq("id", saved_id).execute()
        if perfil_auto.data:
            st.session_state.perfil_profissional = perfil_auto.data[0]
            st.session_state.usuario_logado = type('obj', (object,), {'id': saved_id})()
    except Exception:
        pass

# ================= 3. GERADORES DE PDF EXECUTIVOS =================
def sanitizar_texto(texto):
    substituicoes = {
        '**': '', '###': '', '##': '', '#': '', '–': '-', '—': '-',
        '≥': '>=', '≤': '<=', '“': '"', '”': '"', '’': "'", '‘': "'",
        '•': '-', '|': ' - ', '>': ''
    }
    for k, v in substituicoes.items():
        texto = texto.replace(k, v)
        
    chars = []
    for c in texto:
        try:
            c.encode('latin-1')
            chars.append(c)
        except UnicodeEncodeError:
            chars.append(' ')
    return "".join(chars)

def baixar_logo_temporario(url):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            conteudo = response.read()
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img = Image.open(io.BytesIO(conteudo))
            img.thumbnail((300, 100), Image.Resampling.LANCZOS)
            img.save(tmp.name, format="PNG")
            return tmp.name
    except Exception:
        return None

class PDFLaudo(FPDF):
    def __init__(self, nome_paciente, foco_caso, dados_prof=None, caminho_logo_temp=None):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.nome_paciente = nome_paciente
        self.foco_caso = foco_caso
        self.dados_prof = dados_prof
        self.caminho_logo_temp = caminho_logo_temp

    def header(self):
        self.set_fill_color(197, 168, 128)
        self.rect(0, 0, 210, 14, 'F')
        
        if self.caminho_logo_temp and os.path.exists(self.caminho_logo_temp):
            try:
                self.image(self.caminho_logo_temp, x=10, y=2, h=10)
                self.set_xy(45, 4)
            except Exception:
                self.set_xy(10, 4)
        else:
            self.set_xy(10, 4)
            
        self.set_font("Arial", 'B', 9.5)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, txt="NEXUS ESTETICA - PLANEJAMENTO E CONDUTA CLINICA", ln=True, align='C')
        self.ln(2)
        
        self.set_text_color(44, 62, 80)
        self.set_font("Arial", 'B', 7.5)
        prof_info = ""
        if self.dados_prof:
            conselho_rotulo = self.dados_prof.get('conselho', 'CRBM')
            prof_info = f" | Resp: {self.dados_prof.get('nome')} ({conselho_rotulo} {self.dados_prof.get('registro')})"
        self.cell(0, 4, txt=f"Paciente: {self.nome_paciente} | Foco: {self.foco_caso}{prof_info}", ln=True)
        self.line(10, 21, 200, 21)
        self.ln(3)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", 'I', 6.2)
        self.set_text_color(130, 130, 130)
        aviso_legal = "Nexus Estetica AI: Ferramenta analitica de suporte a decisao clinica. A indicacao, posologia e execucao cabem exclusivamente ao profissional responsavel."
        self.cell(0, 3.5, txt=aviso_legal, ln=True, align='C')
        self.cell(0, 3.5, f"Pagina {self.page_no()}", align='C')

def gerar_pdf(texto_laudo, nome_paciente, foco_caso, dados_prof=None):
    logo_temp = None
    if dados_prof and dados_prof.get("logo_url"):
        logo_temp = baixar_logo_temporario(dados_prof.get("logo_url"))

    pdf = PDFLaudo(nome_paciente, foco_caso, dados_prof, logo_temp)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    pdf.set_font("Arial", size=7.2)
    pdf.set_text_color(30, 30, 30)
    texto_final = sanitizar_texto(texto_laudo)
    
    pdf.multi_cell(0, 3.2, txt=texto_final)
    
    pdf.ln(4)
    y_atual = pdf.get_y()
    
    if y_atual > 225:
        pdf.add_page()
        y_atual = 25
        
    pdf.set_font("Arial", 'I', 6.5)
    pdf.set_text_color(95, 95, 95)
    termo_resp = (
        "RESSALVA REGULATORIA E RESPONSABILIDADE TECNICA: O presente parecer clinico foi emitido com suporte de "
        "inteligencia artificial analitica do Nexus Estetica como ferramenta de auxilio a decisao profissional. "
        "A anamnese soberana, confirmacao diagnostica, indicacao posologica, aplicacao tecnica e o manejo de "
        "quaisquer intercorrencias sao de competencia e responsabilidade etica e tecnica indelegavel do(a) "
        "profissional assistente subscrito(a), nos exatos termos das normativas do seu conselho profissional."
    )
    pdf.multi_cell(0, 3.0, txt=sanitizar_texto(termo_resp))
    
    pdf.ln(5)
    y_pos_termo = pdf.get_y()
    if y_pos_termo > 245:
        pdf.add_page()
        y_pos_termo = 25
        
    y_ass = y_pos_termo + 6
    pdf.set_font("Arial", 'B', 7.5)
    pdf.line(15, y_ass, 95, y_ass)
    pdf.line(115, y_ass, 195, y_ass)
    
    nome_prof = dados_prof.get('nome') if dados_prof else "Responsavel Tecnico"
    reg_prof = f"{dados_prof.get('conselho')} {dados_prof.get('registro')}" if dados_prof else "Registro"
    
    pdf.set_xy(15, y_ass + 2)
    pdf.cell(80, 4, txt=f"{nome_prof} - {reg_prof}", align='C')
    pdf.set_xy(115, y_ass + 2)
    pdf.cell(80, 4, txt=f"{nome_paciente} (Paciente)", align='C')
    
    saida = pdf.output(dest='S')
    
    if logo_temp and os.path.exists(logo_temp):
        try:
            os.remove(logo_temp)
        except Exception:
            pass

    return saida.encode('latin-1') if isinstance(saida, str) else bytes(saida)

def gerar_tcle_pdf(nome_paciente, foco_caso, dados_prof=None, caminho_assinatura_img=None):
    logo_temp = None
    if dados_prof and dados_prof.get("logo_url"):
        logo_temp = baixar_logo_temporario(dados_prof.get("logo_url"))

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    pdf.set_fill_color(197, 168, 128)
    pdf.rect(0, 0, 210, 14, 'F')
    
    if logo_temp and os.path.exists(logo_temp):
        try:
            pdf.image(logo_temp, x=10, y=2, h=10)
        except Exception:
            pass

    pdf.set_font("Arial", 'B', 9.5)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 6, txt="TERMO DE CONSENTIMENTO LIVRE E ESCLARECIDO (TCLE) E USO DE IMAGEM", ln=True, align='C')
    
    pdf.ln(4)
    pdf.set_text_color(44, 62, 80)
    pdf.set_font("Arial", 'B', 8)
    nome_prof = dados_prof.get('nome') if dados_prof else "Responsavel Tecnico"
    reg_prof = f"{dados_prof.get('conselho')} {dados_prof.get('registro')}" if dados_prof else "Registro"
    
    pdf.cell(0, 5, txt=f"Paciente: {nome_paciente} | Profissional: {nome_prof} ({reg_prof})", ln=True)
    pdf.line(10, 25, 200, 25)
    pdf.ln(4)
    
    texto_tcle = f"""
1. DECLARACAO DE CONSENTIMENTO E ESCLARECIMENTO CLINICO
Eu, {nome_paciente}, declaro que fui devidamente avaliado(a) e esclarecido(a) pelo(a) profissional {nome_prof} sobre o diagnostico etiologico facial, plano de tratamento personalizado ({foco_caso}), riscos inerentes, contraindicacoes e cuidados requeridos.

2. PROCEDIMENTOS PREVISTOS NO PLANO CLINICO
Declaro estar ciente de que as condutas prescritas podem envolver o uso de neuromoduladores (toxina botulinica), preenchedores absorviveis (acido hialuronico), bioestimuladores de colageno (PLLA/CaHA), fios de sustentacao (PDO), esvaziadores enzimaticos, biorregeneradores dérmicos (PDRN) ou tecnologias associadas, segundo o plano sequencial individual.

3. RISCOS, INTERCORRENCIAS E RESPOSTA BIOLOGICA INDIVIDUAL
Fui advertido(a) de que os procedimentos esteticos injetaveis e minimamente invasivos envolvem respostas biologicas individuais, podendo ocorrer:
- Edema (inchaco), eritema (vermelhidao), sensibilidade dolorosa local e hematomas/equimoses transitorios.
- Reacoes inflamatorias, formacao de nodulos palpaveis ou granulomas, passíveis de intervencao clinica e medicamentosa.
- Assimetrias temporarias decorrentes de tonus muscular ou acomodacao de materiais, requerendo reavaliacao em 15 a 30 dias.
- Risco vascular (isquemia/oclusao arterial), sendo informado(a) sobre a existencia de protocolos imediatos de resgate com hialuronidase e condutas de emergencia.

4. COMPROMISSO COM AS ORIENTACOES POS-PROCEDIMENTO
Comprometo-me a seguir rigorosamente todas as instrucoes pós-aplicacao (repouso de atividades fisicas intensas, fotoprotecao estrita, evitar manipulacao ou pressao local, cumprir regras de massagem quando indicadas e comparecer a consulta de retorno).

5. PRIVACIDADE, LGPD E PROCESSAMENTO SEGURO DE DADOS
Autorizo a captura e arquivamento seguro de fotografias de antes, durante e apos os procedimentos para fins exclusivos de prontuario clinico, documentacao medico-legal e acompanhamento evolutivo, em conformidade com a Lei Geral de Protecao de Dados (LGPD). Estou ciente de que ferramentas analiticas seguras de suporte inteligente sao empregadas sob sigilo profissional rigoroso.
"""
    pdf.set_font("Arial", size=8)
    pdf.multi_cell(0, 3.7, txt=sanitizar_texto(texto_tcle))
    
    pdf.ln(6)
    if pdf.get_y() > 240:
        pdf.add_page()
    y_ass = max(pdf.get_y() + 10, 248)
    if y_ass > 268:
        pdf.add_page()
        y_ass = 40
        
    if caminho_assinatura_img and os.path.exists(caminho_assinatura_img):
        try:
            pdf.image(caminho_assinatura_img, x=130, y=y_ass - 16, w=50, h=15)
        except Exception:
            pass

    pdf.set_font("Arial", 'B', 8)
    pdf.line(15, y_ass, 95, y_ass)
    pdf.line(115, y_ass, 195, y_ass)
    pdf.set_xy(15, y_ass + 3)
    pdf.cell(80, 4, txt=f"{nome_prof} ({reg_prof})", align='C')
    pdf.set_xy(115, y_ass + 3)
    pdf.cell(80, 4, txt=f"{nome_paciente} (Paciente)", align='C')
    
    saida = pdf.output(dest='S')
    
    if logo_temp and os.path.exists(logo_temp):
        try:
            os.remove(logo_temp)
        except Exception:
            pass

    return saida.encode('latin-1') if isinstance(saida, str) else bytes(saida)

# ================= 4. COMPRESSÃO DE IMAGENS E ARMAZENAMENTO =================
def comprimir_imagem(imagem_bytes, max_dim=800, qualidade=80):
    try:
        img = Image.open(io.BytesIO(imagem_bytes))
        if img.mode in ("RGBA", "LA", "P"):
            fundo_branco = Image.new("RGB", img.size, (255, 255, 255))
            fundo_branco.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = fundo_branco
        elif img.mode != "RGB":
            img = img.convert("RGB")
            
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
        return buffer.getvalue()
    except Exception:
        return imagem_bytes

def salvar_fotos_storage(imagens_payload, prof_id, pac_id, pront_id):
    urls_salvas = []
    bucket_nome = "fotos-pacientes"
    timestamp_atual = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for idx, item in enumerate(imagens_payload):
        try:
            bytes_otimizados = comprimir_imagem(item["bytes"])
            rotulo_limpo = item.get("rotulo", f"foto_{idx+1}").replace(" ", "_").replace("/", "-")
            nome_arquivo = f"prof_{prof_id}/pac_{pac_id}/pront_{pront_id}/{timestamp_atual}_{rotulo_limpo}.jpg"
            
            supabase.storage.from_(bucket_nome).upload(
                path=nome_arquivo,
                file=bytes_otimizados,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            
            url_publica = supabase.storage.from_(bucket_nome).get_public_url(nome_arquivo)
            urls_salvas.append(url_publica)
        except Exception as e:
            st.warning(f"Aviso ao salvar foto {idx+1} no storage: {e}")
            
    return urls_salvas

def salvar_pdfs_storage(pdf_plano_bytes, pdf_tcle_bytes, prof_id, pac_id, pront_id):
    bucket_nome = "documentos-pacientes"
    timestamp_atual = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_plano, url_tcle = None, None
    
    try:
        nome_plano = f"prof_{prof_id}/pac_{pac_id}/pront_{pront_id}/Plano_{timestamp_atual}.pdf"
        supabase.storage.from_(bucket_nome).upload(
            path=nome_plano,
            file=pdf_plano_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        url_plano = supabase.storage.from_(bucket_nome).get_public_url(nome_plano)
    except Exception as e:
        st.warning(f"Aviso ao salvar PDF do Plano no storage: {e}")

    try:
        nome_tcle = f"prof_{prof_id}/pac_{pac_id}/pront_{pront_id}/TCLE_{timestamp_atual}.pdf"
        supabase.storage.from_(bucket_nome).upload(
            path=nome_tcle,
            file=pdf_tcle_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        url_tcle = supabase.storage.from_(bucket_nome).get_public_url(nome_tcle)
    except Exception as e:
        st.warning(f"Aviso ao salvar PDF do TCLE no storage: {e}")
        
    return url_plano, url_tcle

def gerar_laudo_multimodal(prompt_texto, imagens_payload):
    try:
        client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY.strip(),
            timeout=140.0,
            max_retries=2
        )
        
        conteudo_mensagem = []
        for item in imagens_payload:
            bytes_jpeg = comprimir_imagem(item["bytes"])
            dados_b64 = base64.b64encode(bytes_jpeg).decode("utf-8")
            
            rotulo = item.get("rotulo", "Foto Clínica")
            conteudo_mensagem.append({
                "type": "text",
                "text": f"--- {rotulo} ---"
            })
            conteudo_mensagem.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": dados_b64
                }
            })
            
        conteudo_mensagem.append({
            "type": "text",
            "text": prompt_texto
        })
        
        resposta = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=6000,
            system="Voce e o Nexus Estetica. Responda imediatamente com precisao executiva, utilizando topicos diretos. E terminantemente proibido truncar ou interromper a conclusao de qualquer secao.",
            messages=[{"role": "user", "content": conteudo_mensagem}]
        )
        
        texto_final = []
        for bloco in resposta.content:
            if getattr(bloco, 'type', None) == 'text' and bloco.text:
                texto_final.append(bloco.text)
            elif hasattr(bloco, 'text') and bloco.text:
                texto_final.append(bloco.text)
            elif isinstance(bloco, dict) and bloco.get('type') == 'text':
                texto_final.append(bloco.get('text', ''))
                
        resultado_str = "\n\n".join(texto_final).strip()
        if resultado_str:
            return resultado_str
            
        motivo = getattr(resposta, 'stop_reason', 'Desconhecido')
        return f"Erro: Resposta vazia da API (Motivo: {motivo})"
        
    except anthropic.APIConnectionError as e:
        return f"Erro de conexao com a Anthropic: {e}."
    except anthropic.BadRequestError as e:
        return f"Erro de requisicao na Anthropic (BadRequest): {e}."
    except Exception as e:
        return f"Erro inesperado na IA: {e}"

# ================= 5. INGESTÃO RESUMIDA E ECONÔMICA DO STORAGE =================
def carregar_conhecimento():
    texto_base = ""
    documentos_identificados = []
    
    try:
        arquivos_bucket = supabase.storage.from_("documentos-estetica").list()
        if arquivos_bucket and len(arquivos_bucket) > 0:
            for item in arquivos_bucket:
                nome_arq = item.get("name")
                if nome_arq and nome_arq.endswith(".pdf"):
                    try:
                        arquivo_bytes = supabase.storage.from_("documentos-estetica").download(nome_arq)
                        leitor = PyPDF2.PdfReader(io.BytesIO(arquivo_bytes))
                        total_pags = len(leitor.pages)
                        nome_lower = nome_arq.lower()
                        txt = ""
                        
                        if "resolucao" in nome_lower or "cfbm" in nome_lower or "cfo" in nome_lower:
                            for idx in range(min(2, total_pags)):
                                t = leitor.pages[idx].extract_text()
                                if t: txt += t + "\n"
                        elif "bula" in nome_lower:
                            pags_alvo = [0, 1, 2]
                            for idx in pags_alvo:
                                if idx < total_pags:
                                    t = leitor.pages[idx].extract_text()
                                    if t: txt += t + "\n"
                        else:
                            for idx in range(min(3, total_pags)):
                                t = leitor.pages[idx].extract_text()
                                if t: txt += t + "\n"
                                
                        if txt.strip():
                            documentos_identificados.append(nome_arq)
                            texto_base += f"\n[{nome_arq}]: " + txt[:2000].replace('\n', ' ') + "\n"
                    except Exception:
                        continue
                        
            if documentos_identificados:
                return texto_base, f"{len(documentos_identificados)} diretrizes ativas via Supabase Storage (Otimizado).", documentos_identificados
    except Exception:
        pass

    try:
        for arquivo in sorted(os.listdir(".")):
            if arquivo.endswith(".pdf") and not arquivo.startswith("Plano_") and not arquivo.startswith("Prontuario_") and not arquivo.startswith("TCLE_"):
                documentos_identificados.append(arquivo)
        if documentos_identificados:
            return texto_base, f"{len(documentos_identificados)} documentos locais ativos.", documentos_identificados
    except Exception:
        pass
        
    return "", "Nenhum documento encontrado.", []

# ================= 6. AUTENTICAÇÃO COM SESSÃO PERSISTENTE =================
if not st.session_state.usuario_logado:
    st.markdown("<h2 style='text-align: center; color: #2C3E50;'>✨ Nexus Estética - Acesso Profissional</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Ambiente de Prontuário Médico-Legal e Suporte à Decisão</p>", unsafe_allow_html=True)
    
    _, col_central, _ = st.columns([1, 2, 1])
    with col_central:
        aba_login, aba_registro = st.tabs(["🔑 Acessar Conta", "📝 Novo Cadastro Profissional"])
        with aba_login:
            email_login = st.text_input("E-mail Profissional", key="log_email")
            senha_login = st.text_input("Senha", type="password", key="log_pass")
            if st.button("ENTRAR NO SISTEMA", use_container_width=True, type="primary"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email_login, "password": senha_login})
                    st.session_state.usuario_logado = res.user
                    perfil = supabase.table("profissionais").select("*").eq("id", res.user.id).execute()
                    if perfil.data:
                        st.session_state.perfil_profissional = perfil.data[0]
                    st.query_params["user_id"] = res.user.id
                    st.success("Acesso autorizado com sucesso!")
                    st.rerun()
                except Exception:
                    st.error("Credenciais inválidas.")

        with aba_registro:
            nome_cad = st.text_input("Nome Completo", placeholder="Dr(a). Nome Sobrenome")
            col_cad1, col_cad2 = st.columns(2)
            with col_cad1:
                conselho_cad = st.selectbox("Conselho Profissional", list(MAPA_CONSELHOS.keys()))
            with col_cad2:
                reg_cad = st.text_input("Nº Registro", placeholder="Ex: 12345/RJ")
            email_cad = st.text_input("E-mail para Acesso", key="cad_email")
            senha_cad = st.text_input("Definir Senha", type="password", key="cad_pass")
            if st.button("CRIAR CONTA PROFISSIONAL", use_container_width=True):
                if not nome_cad or not reg_cad or not email_cad or not senha_cad:
                    st.error("Preencha todos os campos cadastrais.")
                else:
                    try:
                        res = supabase.auth.sign_up({"email": email_cad, "password": senha_cad})
                        supabase.table("profissionais").insert({
                            "id": res.user.id,
                            "nome": nome_cad,
                            "conselho": conselho_cad,
                            "registro": reg_cad,
                            "email": email_cad,
                            "limite_laudos_mes": 30,
                            "laudos_gerados_mes": 0,
                            "mes_referencia_cota": datetime.now().strftime("%Y-%m")
                        }).execute()
                        st.success("Conta criada! Faça login na aba ao lado.")
                    except Exception as e:
                        st.error(f"Erro ao criar conta: {e}")
    st.stop()

# ================= 7. PAINEL PRINCIPAL & CONTROLE DE COTA =================
prof = st.session_state.perfil_profissional
prof_id = st.session_state.usuario_logado.id
conselho_atual = prof.get('conselho', 'CRBM') if prof else 'CRBM'
dados_conselho = MAPA_CONSELHOS.get(conselho_atual, MAPA_CONSELHOS['CRBM'])

# Lógica de Virada de Mês e Leitura de Cota
mes_atual_str = datetime.now().strftime("%Y-%m")
limite_laudos = prof.get("limite_laudos_mes", 30) or 30
laudos_usados = prof.get("laudos_gerados_mes", 0) or 0
mes_registrado = prof.get("mes_referencia_cota", mes_atual_str)

if mes_registrado != mes_atual_str:
    try:
        supabase.table("profissionais").update({
            "laudos_gerados_mes": 0,
            "mes_referencia_cota": mes_atual_str
        }).eq("id", prof_id).execute()
        laudos_usados = 0
        prof["laudos_gerados_mes"] = 0
        prof["mes_referencia_cota"] = mes_atual_str
        st.session_state.perfil_profissional = prof
    except Exception:
        pass

cota_esgotada = (laudos_usados >= limite_laudos)
saldo_restante = max(0, limite_laudos - laudos_usados)

# Informações de perfil também disponíveis na barra lateral (desktop)
with st.sidebar:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", use_container_width=True)
    else:
        st.markdown("### 💎 Nexus Estética")
    
    st.markdown(f"**Profissional:** {prof.get('nome') if prof else 'Conectado'}")
    if prof:
        st.caption(f"{conselho_atual}: {prof.get('registro')} ({dados_conselho['termo_profissional']})")

    with st.expander("📊 Plano & Cota de Laudos", expanded=True):
        st.markdown(f"**Ciclo Atual:** `{mes_atual_str}`")
        st.progress(min(1.0, laudos_usados / max(1, limite_laudos)))
        st.caption(f"Utilizados: **{laudos_usados}** de **{limite_laudos}** laudos mensais.")
        if cota_esgotada:
            st.error("⚠️ Limite mensal atingido! Contate o suporte para upgrade de plano.")
        else:
            st.success(f"Disponíveis: **{saldo_restante}** avaliações neste mês.")
    
    if st.button("Sair / Desconectar", key="btn_sair_sidebar"):
        st.session_state.usuario_logado = None
        st.session_state.perfil_profissional = None
        st.session_state.laudo_ativo = None
        st.session_state.pdf_plano_bytes = None
        st.session_state.pdf_tcle_bytes = None
        st.session_state.ultimo_pront_id = None
        st.session_state.ultimo_pac_id = None
        if "user_id" in st.query_params:
            del st.query_params["user_id"]
        st.rerun()

# ================= CABEÇALHO PRINCIPAL =================
if os.path.exists("logo.jpg"):
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        st.image("logo.jpg", width=140)

st.title("✨ Nexus Estética - Suporte à Decisão Clínica")
st.caption(f"Profissional: **{prof.get('nome')}** | {conselho_atual} {prof.get('registro')} | Cota: **{saldo_restante}** laudos restantes")

# ================= SOLUÇÃO DEFINITIVA: FORMULÁRIO ACESSÍVEL EM QUALQUER TELA =================
# O formulário da anamnese agora fica dentro de um Expander nativo e direto no corpo do app
# Isso garante que no celular NINGUÉM fique dependendo de puxar lateral nem sofra com menus sumidos.

with st.expander("📋 ABRIR FICHA DO PACIENTE & ANAMNESE CLÍNICA", expanded=st.session_state.exibir_formulario_mobile):
    modo_atendimento = st.radio("Tipo de Atendimento", ["Novo Paciente", "Consulta de Retorno"], horizontal=True)
    
    paciente_selecionado = None
    prontuario_referencia = None
    
    if modo_atendimento == "Consulta de Retorno":
        pacientes_res = supabase.table("pacientes").select("*").eq("profissional_id", prof_id).order("nome").execute()
        lista_pacientes = pacientes_res.data
        if lista_pacientes:
            opcoes_pacientes = {p['nome']: p for p in lista_pacientes}
            escolha = st.selectbox("Selecione o Paciente Cadastrado", list(opcoes_pacientes.keys()))
            paciente_selecionado = opcoes_pacientes[escolha]
            
            historico = supabase.table("prontuarios").select("*").eq("paciente_id", paciente_selecionado['id']).order("data_atendimento", desc=True).execute()
            prontuarios_historico = historico.data
            
            if prontuarios_historico:
                st.caption(f"Total de consultas registradas: {len(prontuarios_historico)}")
                opcoes_consultas = {
                    f"{p['data_atendimento'][:10]} - {p.get('procedimento', 'Avaliação')}": p 
                    for p in prontuarios_historico
                }
                escolha_consulta = st.selectbox("Prontuário de Referência (Histórico)", list(opcoes_consultas.keys()))
                prontuario_referencia = opcoes_consultas[escolha_consulta]
            else:
                st.info("Paciente sem consultas anteriores registradas.")
        else:
            st.warning("Nenhum paciente cadastrado.")

    nome_padrao = paciente_selecionado['nome'] if paciente_selecionado else ""
    idade_padrao = int(paciente_selecionado['idade']) if paciente_selecionado else 55
    genero_padrao = paciente_selecionado.get('genero', 'Feminino') if paciente_selecionado else "Feminino"
    
    nome = st.text_input("Nome do Paciente", value=nome_padrao, placeholder="Ex: Claudia Rosa")
    col1, col2 = st.columns(2)
    with col1:
        idade = st.number_input("Idade", min_value=18, max_value=100, value=idade_padrao)
    with col2:
        idx_gen = ["Feminino", "Masculino", "Outro"].index(genero_padrao) if genero_padrao in ["Feminino", "Masculino", "Outro"] else 0
        genero = st.selectbox("Gênero", ["Feminino", "Masculino", "Outro"], index=idx_gen)
        
    queixa_default = "Consulta de retorno: avaliar resposta biológica tecidual, simetria muscular e planejar próximas condutas." if modo_atendimento == "Consulta de Retorno" else "Queixa de olhar cansado, rugas na testa, bigode chinês e sensação de peso no terço inferior (jowls)."
    queixa = st.text_area("Queixa Principal / Motivo da Consulta", value=queixa_default)
    
    foco_avaliacao = st.selectbox("Escopo da Avaliação Clínica", [
        "Consulta de Retorno / Ajuste e Segunda Sessão",
        "Avaliação Facial Global (Indicação Livre de Condutas)",
        "Foco em Terço Superior (Olhar, Glabela e Fronte)",
        "Foco em Sustentação e Vetores (Terço Médio, Jowls e Mento)",
        "Foco em Contorno Mandibular e Submento (Papada / Gordura)",
        "Foco em Biorregeneração, Qualidade de Pele e Flacidez"
    ])
    
    # ================= ANAMNESE ESTRUTURADA EM 5 BLOCOS CLÍNICOS =================
    aba_hab, aba_seg, aba_farm, aba_vasc, aba_est = st.tabs([
        "☀️ Hábitos", "🛡️ Segurança", "💊 Fármacos", "🩸 Vascular", "💉 Histórico Estético"
    ])
    
    with aba_hab:
        rotina_sol = st.selectbox("Exposição Solar", ["Baixa (< 30 min)", "Moderada (30m a 2h)", "Alta (> 2h)"])
        usa_fps = st.checkbox("Usa protetor solar diariamente", value=True)
        tabagismo = st.checkbox("Tabagista ativo")
        etilismo = st.checkbox("Consumo frequente de álcool")
        atividade_intensa = st.checkbox("Pratica musculação / treino intenso (alta demanda metabólica)")

    with aba_seg:
        gestante_lactante = st.checkbox("Gestante ou Lactante")
        doenca_neuromuscular = st.checkbox("Doença Neuromuscular (Miastenia gravis, Eaton-Lambert)")
        doenca_autoimune = st.checkbox("Doença Autoimune Ativa (Lúpus, Artrite, Psoríase)")
        diabetes_descompensada = st.checkbox("Diabetes Mellitus descompensada")
        tireoide_descompensada = st.checkbox("Disfunção tireoidiana descompensada (Hipotireoidismo/Hashimoto)")
        infeccao_local = st.checkbox("Lesão inflamatória / Infecção ativa na face")

    with aba_farm:
        alergia_ovo_leite = st.checkbox("Alergia a Albumina Humana ou Caseína")
        alergia_anestesicos = st.checkbox("Alergia a Lidocaína ou Anestésicos Locais")
        alergia_medicamentos = st.checkbox("Alergia medicamentosa (AINEs, Dipirona, Antibióticos)")
        roacutan_recente = st.checkbox("Uso de Isotretinoína oral (Roacutan) nos últimos 12 meses")
        corticoide_imuno = st.checkbox("Uso contínuo de Corticosteroides ou Imunossupressores")
        uso_aminoglicosideos = st.checkbox("Uso de Aminoglicosídeos ou Relaxantes Musculares")

    with aba_vasc:
        uso_aas = st.checkbox("Uso de AAS, Anticoagulantes ou Antiagregantes (NOACs, Ginkgo)")
        historico_ptose = st.checkbox("Histórico de ptose palpebral prévia pós-toxina")
        historico_herpes = st.checkbox("Histórico de Herpes Simples Labial/Facial recorrente")
        tendencia_queloide = st.checkbox("Tendência a queloide ou cicatriz hipertrófica")
        cirurgia_facial_previa = st.checkbox("Cirurgia facial prévia (Rinoplastia, Blefaroplastia, Lifting)")

    with aba_est:
        ja_fez_toxina = st.checkbox("Já aplicou Toxina anteriormente", value=True if modo_atendimento == "Consulta de Retorno" else False)
        meses_ultima_toxina = 1 if modo_atendimento == "Consulta de Retorno" else 12
        if ja_fez_toxina:
            meses_ultima_toxina = st.number_input("Meses desde a última aplicação de toxina", min_value=0, max_value=60, value=meses_ultima_toxina)
        preenchedor_previo = st.checkbox("Possui preenchedor absorvível prévio (Ácido Hialurônico)")
        bioestimulador_previo = st.checkbox("Já realizou Bioestimulador de Colágeno (PLLA, CaHA ou Fios)")
        polimero_definitivo = st.checkbox("⚠️ Presença de Material Definitivo (PMMA, Silicone, Metacrilato)")
        intercorrencia_previa = st.checkbox("Histórico de necrose vascular, nódulo inflamatório ou granuloma")

# ================= 9. ABA DE HISTÓRICO VISUAL (RETORNO) =================
if modo_atendimento == "Consulta de Retorno" and prontuario_referencia:
    with st.expander(f"📁 Histórico Clínico Selecionado ({prontuario_referencia['data_atendimento'][:10]} - {prontuario_referencia.get('procedimento', '')})", expanded=True):
        col_hist1, col_hist2 = st.columns([1, 1])
        with col_hist1:
            st.markdown("**Documentos da Consulta Anterior:**")
            if prontuario_referencia.get("pdf_plano_url"):
                st.markdown(f"📄 [Baixar Plano de Tratamento Anterior]({prontuario_referencia['pdf_plano_url']})")
            if prontuario_referencia.get("pdf_tcle_url"):
                st.markdown(f"📝 [Baixar TCLE Anterior]({prontuario_referencia['pdf_tcle_url']})")
            if not prontuario_referencia.get("pdf_plano_url") and not prontuario_referencia.get("pdf_tcle_url"):
                st.caption("PDFs arquivados no banco de dados para esta consulta.")
                
        with col_hist2:
            st.markdown("**Conduta Registrada no Parecer Anterior:**")
            texto_resumido = prontuario_referencia.get("laudo_texto", "")
            if len(texto_resumido) > 400:
                st.caption(texto_resumido[:400] + "...")
            else:
                st.caption(texto_resumido)
                
        fotos_anteriores = prontuario_referencia.get("fotos_urls")
        if fotos_anteriores and isinstance(fotos_anteriores, list):
            st.markdown("**Fotos de Base da Consulta Anterior:**")
            col_f_ant = st.columns(min(len(fotos_anteriores), 4))
            for i_foto, url_f in enumerate(fotos_anteriores):
                with col_f_ant[i_foto % 4]:
                    st.image(url_f, caption=f"Anterior {i_foto+1}", use_container_width=True)

# ================= 10. PROTOCOLO FOTOGRÁFICO =================
st.subheader("📷 Protocolo Fotográfico Clínico Padronizado")
st.caption("Organize as fotografias de acordo com as expressões para análise do sistema.")

col_upload1, col_upload2 = st.columns(2)

with col_upload1:
    foto_repouso = st.file_uploader(
        "1. Face Frontal - REPOUSO (Mandatória)",
        type=["jpg", "jpeg", "png"],
        key="f_repouso",
        help="Rosto relaxado, sem expressões."
    )
    foto_glabela = st.file_uploader(
        "3. Dinâmica - GLABELA / BRAVO",
        type=["jpg", "jpeg", "png"],
        key="f_glabela"
    )

with col_upload2:
    foto_frontal = st.file_uploader(
        "2. Dinâmica - MÚSCULO FRONTAL / TESTA",
        type=["jpg", "jpeg", "png"],
        key="f_frontal"
    )
    foto_sorriso = st.file_uploader(
        "4. Dinâmica - SORRISO FORÇADO",
        type=["jpg", "jpeg", "png"],
        key="f_sorriso"
    )

with st.expander("📐 Fotografias Complementares de Contorno (Perfil e Oblíquas)"):
    col_lat1, col_lat2 = st.columns(2)
    with col_lat1:
        foto_perfil_dir = st.file_uploader("Perfil Direito (90°)", type=["jpg", "jpeg", "png"], key="f_p_dir")
        foto_obliqua_dir = st.file_uploader("Oblíqua Direita (45°)", type=["jpg", "jpeg", "png"], key="f_o_dir")
    with col_lat2:
        foto_perfil_esq = st.file_uploader("Perfil Esquerdo (90°)", type=["jpg", "jpeg", "png"], key="f_p_esq")
        foto_obliqua_esq = st.file_uploader("Oblíqua Esquerda (45°)", type=["jpg", "jpeg", "png"], key="f_o_esq")

imagens_payload = []
mapa_fotos = [
    ("FOTO 1: FACE FRONTAL EM REPOUSO", foto_repouso),
    ("FOTO 2: DINAMICA FRONTAL (TESTA ELEVADA)", foto_frontal),
    ("FOTO 3: DINAMICA GLABELA (FRANZIR)", foto_glabela),
    ("FOTO 4: DINAMICA SORRISO (PERIORBICULAR)", foto_sorriso),
    ("FOTO 5: PERFIL DIREITO (90 GRAUS)", foto_perfil_dir),
    ("FOTO 6: PERFIL ESQUERDO (90 GRAUS)", foto_perfil_esq),
    ("FOTO 7: OBLIQUA DIREITA (45 GRAUS)", foto_obliqua_dir),
    ("FOTO 8: OBLIQUA ESQUERDA (45 GRAUS)", foto_obliqua_esq)
]

fotos_ativas = [(rotulo, f) for rotulo, f in mapa_fotos if f is not None]
if fotos_ativas:
    cols_prev = st.columns(min(len(fotos_ativas), 4))
    for idx, (rotulo, arq) in enumerate(fotos_ativas):
        with cols_prev[idx % 4]:
            st.image(arq, caption=rotulo, use_container_width=True)
            imagens_payload.append({
                "tipo": arq.type,
                "bytes": arq.getvalue(),
                "rotulo": rotulo
            })

conhecimento_atual, msg_status, lista_docs = carregar_conhecimento()

st.divider()
rotulo_botao = "GERAR PLANO DE RETORNO E EVOLUÇÃO" if modo_atendimento == "Consulta de Retorno" else "⚡ DIAGNOSTICAR E PLANEJAR TRATAMENTO"
gerar = st.button(rotulo_botao, type="primary", use_container_width=True, disabled=cota_esgotada)
if cota_esgotada:
    st.error("❌ Emissão bloqueada: cota de laudos esgotada neste ciclo.")

# ================= 11. PROCESSAMENTO MULTI-CONSELHO =================
if gerar:
    if cota_esgotada:
        st.error("Sua cota mensal de avaliações foi esgotada.")
    elif not nome:
        st.error("Preencha o nome do paciente no formulário acima.")
    elif not foto_repouso:
        st.error("A Foto 1 (Face Frontal em Repouso) é obrigatória para definir os parâmetros basais.")
    else:
        with st.spinner("Processando parecer com enquadramento regulatório..."):
            anamnese_dict = {
                "idade": idade, "genero": genero, "queixa": queixa, "escopo": foco_avaliacao,
                "habitos": {
                    "sol": rotina_sol, "fps": usa_fps, "tabaco": tabagismo, 
                    "alcool": etilismo, "treino_intenso": atividade_intensa
                },
                "seguranca_sistemica": {
                    "gestante_lactante": gestante_lactante,
                    "neuromuscular": doenca_neuromuscular, 
                    "autoimune_ativa": doenca_autoimune, 
                    "diabetes_descompensada": diabetes_descompensada,
                    "tireoide_descompensada": tireoide_descompensada,
                    "infeccao_local": infeccao_local
                },
                "farmacologia_alergias": {
                    "alergia_albumina": alergia_ovo_leite, 
                    "alergia_lidocaina": alergia_anestesicos,
                    "alergia_medicamentosa": alergia_medicamentos, 
                    "roacutan_12m": roacutan_recente,
                    "corticoides_imuno": corticoide_imuno,
                    "aminoglicosideos": uso_aminoglicosideos
                },
                "vascular_cicatrizacao": {
                    "anticoagulante_aas": uso_aas, 
                    "historico_ptose": historico_ptose, 
                    "herpes_recorrente": historico_herpes, 
                    "queloide": tendencia_queloide,
                    "cirurgia_facial_previa": cirurgia_facial_previa
                },
                "passado_estetico": {
                    "toxina_previa": ja_fez_toxina, 
                    "meses_ultima_toxina": meses_ultima_toxina if ja_fez_toxina else None, 
                    "preenchedor_ah": preenchedor_previo, 
                    "bioestimulador_previo": bioestimulador_previo,
                    "alerta_polimero_definitivo_pmma": polimero_definitivo,
                    "intercorrencia_previa": intercorrencia_previa
                }
            }
            
            contexto_historico = ""
            if modo_atendimento == "Consulta de Retorno" and prontuario_referencia:
                contexto_historico = f"""
                HISTÓRICO DE ATENDIMENTO ANTERIOR (CONSULTA DE {prontuario_referencia['data_atendimento'][:10]}):
                - Procedimento anterior realizado: {prontuario_referencia.get('procedimento')}
                - Parecer e condutas anteriores: {prontuario_referencia.get('laudo_texto')[:1500]}
                DIRETRIZ DE RETORNO:
                Esta é uma consulta de acompanhamento/evolução. Avalie a resposta biológica, simetria muscular e planeje a próxima sessão.
                """
            
            texto_suporte_imagem = ""
            if imagens_payload:
                texto_suporte_imagem = f"""
                ANÁLISE FOTOGRÁFICA ATIVA ({len(imagens_payload)} imagem/imagens anexadas com identificação de mímica e ângulos):
                
                DIRETRIZES MANDATÓRIAS DE LEITURA ANATÔMICA:
                1. A FOTO 1 (FACE FRONTAL EM REPOUSO) é o único padrão basal para avaliar simetria global, proporções dos terços faciais, bolsas, ptose e abertura ocular.
                2. REGRA DE EXCLUSÃO CRÍTICA (FOTO 2 - FRONTAL/TESTA): A elevação das sobrancelhas gera retração palpebral e exposição de esclera reflexas. É TERMINANTEMENTE PROIBIDO classificar essa abertura ocular na Foto 2 como 'olhar proeminente', 'exoftalmia' ou 'esclera aparente'. Foque unicamente na classificação das rugas dinâmicas da testa.
                3. A FOTO 3 (GLABELA) destina-se unicamente à força dos músculos corrugadores e prócero.
                4. A FOTO 4 (SORRISO) destina-se às linhas perioculares (orbicular dos olhos) e elevação zigomática.
                5. IMAGENS DE PERFIL/OBLÍQUAS (se presentes): Utilize-as especificamente para avaliar ângulo da mandíbula, perda de contorno pré-jowl, projeção do mento (plano estético de Ricketts) e sustentação malar tridimensional.
                """
            
            prompt_mestre = f"""
            DADOS DO PACIENTE:
            Paciente: {nome}, {idade} anos, Gênero: {genero}.
            Tipo de Consulta: {modo_atendimento}
            Queixa Relatada: "{queixa}"
            Escopo da Avaliação: {foco_avaliacao}
            
            ENQUADRAMENTO PROFISSIONAL E CONSELHO DE CLASSE:
            - Conselho: {conselho_atual} ({dados_conselho['orgao']})
            - Categoria Profissional: {dados_conselho['termo_profissional']}
            - Amparo Regulatório Específico: {dados_conselho['resolucoes']}
            - Limites de Escopo do Conselho: {dados_conselho['limites']}
            
            Anamnese Detalhada e Rastreio Clínico: {json.dumps(anamnese_dict)}
            {contexto_historico}
            {texto_suporte_imagem}

            BASE CIENTÍFICA RESUMIDA:
            {conhecimento_atual}

            DIRETRIZ DE REDAÇÃO CLÍNICA:
            Emita o laudo em formato executivo direto, com tópicos objetivos em marcadores com traço (-). Sem enrolação descritiva. É imperativo concluir 100% de todas as 5 seções até a última linha normativa.

            ESTRUTURA OBRIGATÓRIA (COMPLETE TODAS AS 5 SEÇÕES):
            PARECER DIAGNÓSTICO E PLANO DE TRATAMENTO: {nome}, {idade} anos

            1. DIAGNÓSTICO ETIOLÓGICO E STATUS DE SEGURANÇA
            - Classificação: APTO, APTO COM RESTRIÇÕES ou INAPTO (com ressalva de escopo para {conselho_atual}).
            - Avaliação tecidual por camada (Músculo, Osso, Gordura e Derme em repouso).
            - Rastreio de Riscos da Anamnese (citar expressamente contraindicações ou alertas para PMMA prévio, Roacutan, anticoagulantes, diabetes/tireoide, alergias e herpes se marcados).

            2. PROCEDIMENTOS INDICADOS E SEQUÊNCIA CRONOLÓGICA (PLANO TERAPÊUTICO)
            - Sessão 1 (Prioridade Imediata): técnica principal e justificativa.
            - Sessão 2 (Complementar): intervalo e objetivo.
            - Sessão 3 (Manutenção): intervalo e refinamento.
            - Procedimentos desaconselhados neste momento e justificativa objetiva (ex: contraindicar bioestimulador em área com PMMA ou microagulhamento com Roacutan recente).

            3. ESPECIFICAÇÕES TÉCNICAS E POSOLOGIA DOS PROCEDIMENTOS ELEITOS
            - Para cada técnica recomendada:
              * Toxina: dosagem em U, reconstituição (2,5 mL/100 U) e músculos-alvo.
              * Ácido Hialurônico: planos anatômicos, cânula 22G vs agulha, aspiração prévia, dosagens e seleção de produto (sem lidocaína se relatada alergia).
              * Bioestimulador (PLLA/CaHA): reconstituição/diluição oficial, técnica em leque e regra dos 5 (massagem 5x/dia, 5 min, 5 dias).
              * Outros (Fios/Desoxicolato/PDRN): doses, planos e intervalos, se indicados.

            4. MARGENS DE SEGURANÇA E PROTOCOLO DE INTERCORRÊNCIAS
            - Zonas nobres e trajetos vasculares de maior risco anatômico nas áreas tratadas (inclusive zonas com fibrose cirúrgica prévia).
            - Protocolo imediato de reversão/intercorrência vascular (conduta imediata com hialuronidase de alta dose em saturação; conduta de nódulos, hematomas e profilaxia de herpes se indicada).
            - Orientações de cuidados imediatos no pós-procedimento e intervalo de retorno.

            5. RESPALDO NORMATIVO E DECLARAÇÃO ÉTICO-LEGAL
            - Amparo legal: citação das normas específicas do conselho ({dados_conselho['resolucoes']}) e limites de atuação ({dados_conselho['limites']}).
            - Literatura de referência: bulas e consensos indexados.
            - DECLARAÇÃO MANDATÓRIA FINAL: 'Este documento é emitido como suporte à decisão clínica baseada em IA. A anamnese presencial, a indicação terapêutica e a execução técnica são de responsabilidade exclusiva e indelegável do(a) profissional assistente.'
            """
            
            laudo = gerar_laudo_multimodal(prompt_mestre, imagens_payload)
            
            if not laudo.startswith("Erro:"):
                novo_contador = laudos_usados + 1
                try:
                    supabase.table("profissionais").update({
                        "laudos_gerados_mes": novo_contador,
                        "mes_referencia_cota": mes_atual_str
                    }).eq("id", prof_id).execute()
                    prof["laudos_gerados_mes"] = novo_contador
                    prof["mes_referencia_cota"] = mes_atual_str
                    st.session_state.perfil_profissional = prof
                except Exception as e_cota:
                    st.warning(f"Aviso ao debitar cota: {e_cota}")

                pac_id = None
                if paciente_selecionado:
                    pac_id = paciente_selecionado['id']
                else:
                    novo_pac = supabase.table("pacientes").insert({
                        "profissional_id": prof_id,
                        "nome": nome,
                        "idade": idade,
                        "genero": genero,
                        "queixa_principal": queixa
                    }).execute()
                    if novo_pac.data:
                        pac_id = novo_pac.data[0]['id']
                
                if pac_id:
                    pdf_plano = gerar_pdf(laudo, nome, foco_avaliacao, prof)
                    pdf_tcle = gerar_tcle_pdf(nome, foco_avaliacao, prof)
                    
                    st.session_state.laudo_ativo = laudo
                    st.session_state.paciente_atendido = nome
                    st.session_state.pdf_plano_bytes = pdf_plano
                    st.session_state.pdf_tcle_bytes = pdf_tcle
                    st.session_state.ultimo_pac_id = pac_id
                    
                    res_pront = supabase.table("prontuarios").insert({
                        "paciente_id": pac_id,
                        "profissional_id": prof_id,
                        "procedimento": foco_avaliacao,
                        "anamnese_dados": anamnese_dict,
                        "laudo_texto": laudo
                    }).execute()
                    
                    if res_pront.data:
                        pront_id = res_pront.data[0]['id']
                        st.session_state.ultimo_pront_id = pront_id
                        
                        fotos_links = []
                        if imagens_payload:
                            fotos_links = salvar_fotos_storage(imagens_payload, prof_id, pac_id, pront_id)
                        
                        url_plano, url_tcle = salvar_pdfs_storage(pdf_plano, pdf_tcle, prof_id, pac_id, pront_id)
                        
                        dados_update = {}
                        if fotos_links:
                            dados_update["fotos_urls"] = fotos_links
                        if url_plano:
                            dados_update["pdf_plano_url"] = url_plano
                        if url_tcle:
                            dados_update["pdf_tcle_url"] = url_tcle
                            
                        if dados_update:
                            try:
                                supabase.table("prontuarios").update(dados_update).eq("id", pront_id).execute()
                            except Exception as e:
                                st.warning(f"Aviso ao vincular links no prontuário: {e}")
            else:
                st.error(laudo)

# ================= 12. EXIBIÇÃO PERSISTENTE E ASSINATURA EM TELA =================
if st.session_state.laudo_ativo:
    st.markdown("---")
    st.subheader(f"📄 Parecer Diagnóstico e Plano Terapêutico Integrado ({st.session_state.paciente_atendido})")
    
    with st.expander("👁️ Visualizar Conteúdo Integral do Parecer Clínico", expanded=True):
        st.markdown(st.session_state.laudo_ativo)
    
    st.divider()
    
    st.subheader("✍️ Assinatura Digital do Paciente (TCLE)")
    st.caption("Solicite ao paciente assinar diretamente no campo abaixo usando o dedo, caneta touch ou mouse.")
    
    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 0)",
        stroke_width=2,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=140,
        width=320,
        drawing_mode="freedraw",
        key="canvas_assinatura_paciente",
    )
    
    if st.button("Gravar Assinatura no TCLE", use_container_width=True):
        if canvas_result.image_data is not None:
            img_data = canvas_result.image_data
            if img_data[:, :, 3].any():
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                    caminho_tmp = tmp_file.name
                    img_pil = Image.fromarray(img_data.astype('uint8'), 'RGBA')
                    img_pil.save(caminho_tmp, format="PNG")
                    
                novo_tcle_bytes = gerar_tcle_pdf(
                    st.session_state.paciente_atendido,
                    foco_avaliacao,
                    prof,
                    caminho_tmp
                )
                st.session_state.pdf_tcle_bytes = novo_tcle_bytes
                
                if st.session_state.ultimo_pront_id and st.session_state.ultimo_pac_id:
                    _, nova_url_tcle = salvar_pdfs_storage(
                        st.session_state.pdf_plano_bytes,
                        novo_tcle_bytes,
                        prof_id,
                        st.session_state.ultimo_pac_id,
                        st.session_state.ultimo_pront_id
                    )
                    if nova_url_tcle:
                        supabase.table("prontuarios").update({"pdf_tcle_url": nova_url_tcle}).eq("id", st.session_state.ultimo_pront_id).execute()
                        
                try:
                    os.remove(caminho_tmp)
                except Exception:
                    pass
                    
                st.success("Assinatura gravada com sucesso no TCLE!")
                st.rerun()
            else:
                st.warning("Assine no quadro antes de clicar no botão.")

    st.markdown("### 📥 Documentos para Download")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button(
            label="⬇️ Baixar Plano de Tratamento Completo (PDF)",
            data=st.session_state.pdf_plano_bytes,
            file_name=f"Plano_Tratamento_{st.session_state.paciente_atendido.replace(' ', '_')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    with col_d2:
        st.download_button(
            label="⬇️ Baixar Termo de Consentimento (TCLE) com Assinatura (PDF)",
            data=st.session_state.pdf_tcle_bytes,
            file_name=f"TCLE_{st.session_state.paciente_atendido.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )