import os
import json
import re
import io
from google import genai
from dotenv import load_dotenv
from PIL import Image

# --- CARREGA AS VARIÁVEIS DO ARQUIVO .ENV ---
load_dotenv()

# --- FUNÇÃO DE MATEMÁTICA E CLASSIFICAÇÃO DE LONGEVIDADE ---
def classificar_marcador_func(nome, valor, ranges, sexo="Masculino"):
    try:
        val_str = str(valor).replace(',', '.').strip()
        match = re.search(r"[-+]?\d*\.\d+|\d+", val_str)
        if not match: return "Análise Padrão"
        val = float(match.group())

        # Adaptar para a separação por sexo se o dicionário tiver essa camada
        if sexo in ranges:
            regras_sexo = ranges[sexo]
        else:
            regras_sexo = ranges
        
        nome_chave = None
        for k in regras_sexo.keys():
            if k.lower() in nome.lower() or nome.lower() in k.lower():
                nome_chave = k
                break
        
        if not nome_chave: return "Análise Padrão"

        r = regras_sexo[nome_chave]
        
        if r['otimo_min'] <= val <= r['otimo_max']: return "Otimizado"
        elif val > r['alerta_max'] or val < (r['otimo_min'] * 0.5): return "Risco Clínico"
        else: return "Alerta Metabólico"
            
    except Exception as e:
        return "Análise Padrão"

# --- CÉREBRO PRINCIPAL DE ANÁLISE (LAUDOS MÉDICOS) ---
def gerar_laudo_clinico(dados_extraidos, diretrizes="", contexto_clinico="", modulo="", sexo="Masculino"):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return json.dumps({"erro": "Chave da API não encontrada no arquivo .env."})
            
        client = genai.Client(api_key=api_key)
        
        # PROMPT 1: ALTA PERFORMANCE E ESPORTE
        if modulo == "Fisiologia do Esporte e Alta Performance":
            prompt = f"""
            Atue como uma Junta Médica e Nutricional de Elite (composta por um Cardiologista do Desporto, um Endocrinologista e um Nutricionista Clínico/Esportivo).
            
            DADOS DO EXAME: {dados_extraidos}
            CONTEXTO CRÍTICO DO PACIENTE (BIOMETRIA E OBJETIVO): {contexto_clinico}
            
            🚨 DIRETRIZ MULTIDISCIPLINAR E MÉDICA ABSOLUTA:
            1. A sua análise DEVE manter e aprofundar os 3 eixos metabólicos fundamentais ('eixo_glicemico', 'eixo_hormonal' e 'eixo_inflamatorio'), integrando a visão médica especialista em cada um deles.
            2. No 'eixo_glicemico', integre a visão Endocrinológica: avalie detalhadamente a glicose, HbA1c e HOMA-IR, calculando o risco de exaustão pancreática e resistência periférica.
            3. No 'eixo_hormonal', analise o perfil gonadal, tireoidiano e adrenal (Testosterona, Cortisol, TSH), medindo a capacidade anabólica vs. estresse catabólico.
            4. No 'eixo_inflamatorio', adote a visão Cardiológica e de Dano Endotelial: analise o perfil lipídico completo (Colesterol, LDL, HDL, Triglicerídeos), o risco aterogênico e a inflamação sistêmica (PCR, CPK).
            5. O campo 'insight_medico' deve complementar com condutas médicas puras (exames de imagem, Doppler, rastreio cardiovascular e conduta preventiva).
            6. Mantenha o Freio Metabólico rigoroso para carboidratos se houver Pré-Diabetes (HbA1c > 5.4%) ou Dislipidemia, limitando-os a 1.5g-2.0g/kg e priorizando gorduras mono/poli-insaturadas (Azeite, Abacate) e proteínas para bater o alvo calórico de treino de forma segura.
            
            Retorne APENAS um formato JSON válido com as seguintes chaves ESTRITAS:
            {{
                "resumo_executivo": "Síntese médica e nutricional ampla do estado do paciente.",
                "alertas_vermelhos": ["alerta crítico 1", "se não houver, envie array vazio"],
                "alertas_composicao": ["alerta InBody/DEXA", "se não enviou inbody, envie array vazio"],
                "eixo_glicemico": "Análise Endocrinológica Detalhada: Avaliação profunda de glicose, insulina, HbA1c, HOMA-IR e dinâmica de captação de nutrientes.",
                "eixo_hormonal": "Análise Endocrinológica e Metabólica: Avaliação do status dos eixos gonadal, tireoidiano, adrenal e balanço anabólico/catabólico.",
                "eixo_inflamatorio": "Análise Cardiológica e Vascular: Avaliação fina do perfil lipídico avançado, risco aterogênico, integridade endotelial, PCR e enzimas de dano tecidual como CPK.",
                "insight_medico": "Diretriz Clínica Médica: Hipóteses diagnósticas de suporte, sugestão de exames complementares de imagem ou funcionais, e conduta médica/farmacológica.",
                "insight_nutricional": "Diretriz Nutricional Geral: Vias nutricionais, sugestão de macros, calorias e suplementação ergogênica ajustadas ao quadro clínico.",
                "estrategia_nutricional": {{
                    "calorias_alvo": "ex: 2400 kcal",
                    "macros": {{
                        "proteinas": "ex: 180g (2.1g/kg)",
                        "carboidratos": "ex: 140g (1.6g/kg) - Ajustado pelo freio metabólico clínico",
                        "gorduras": "ex: 100g (1.1g/kg)"
                    }},
                    "justificativa_clinica": "Justificativa fisiológica integrando a proteção metabólica ao rendimento."
                }},
                "suplementacao_ergogenica": [
                    {{"suplemento": "Nome", "dosagem": "Dose", "justificativa_clinica": "Porquê clínico baseado no sangue"}}
                ],
                "achados": [
                    {{"marcador": "nome", "valor_encontrado": "valor", "valor_referencia": "ref", "status": "status", "analise_fisiologica": "análise contextualizada"}}
                ]
            }}
            """
            
        # PROMPT 2: ENDOCRINOLOGIA, EMAGRECIMENTO E PAINEL COMPLETO
        elif modulo in ["Performance, Emagrecimento e Endocrinologia", "Painel Completo (Bioquímica + Hematologia)"]:
            prompt = f"""
            Atue como um Copiloto Médico Sênior (Cardiologista, Endocrinologista e Nutricionista Clínico).
            DADOS DO EXAME: {dados_extraidos}
            CONTEXTO CRÍTICO DO PACIENTE (BIOMETRIA E OBJETIVO): {contexto_clinico}
            DIRETRIZES: {diretrizes}
            
            🚨 EIXOS METABÓLICOS E DIRETRIZ CLÍNICA:
            Você DEVE preencher detalhadamente os 3 eixos metabólicos cruzados ('eixo_glicemico', 'eixo_hormonal' e 'eixo_inflamatorio') sob uma ótica médica integrada.
            - No 'eixo_glicemico', faça a leitura endocrinológica do status da insulina, HbA1c e glicemia.
            - No 'eixo_hormonal', avalie a função adrenal, tireoidiana e esteroidogênese.
            - No 'eixo_inflamatorio', detalhe a avaliação lipídica cardiológica e marcadores inflamatórios.
            - O campo 'insight_medico' deve propor condutas de rastreio de comorbidades e intervenção preventiva.
            - Siga o freio metabólico de carboidratos (1.0g a 1.5g/kg) se houver dislipidemia ou resistência insulínica.
            
            Retorne APENAS um formato JSON válido com as seguintes chaves ESTRITAS:
            {{
                "resumo_executivo": "Síntese médica geral.",
                "alertas_vermelhos": [],
                "alertas_composicao": [],
                "eixo_glicemico": "Análise detalhada do metabolismo da glicose e insulina sob a ótica endocrinológica.",
                "eixo_hormonal": "Avaliação glandular e hormonal abrangente.",
                "eixo_inflamatorio": "Análise cardiológica do perfil lipídico e marcadores de inflamação vascular.",
                "insight_medico": "Diretriz Clínica: Exames de imagem/rastreio recomendados e conduta terapêutica/preventiva.",
                "insight_nutricional": "Diretriz Nutricional Geral: Vias nutricionais, sugestão de macros, calorias e suplementação ergogênica ajustadas ao quadro clínico.",
                "estrategia_nutricional": {{
                    "calorias_alvo": "...",
                    "macros": {{ "proteinas": "...", "carboidratos": "...", "gorduras": "..." }},
                    "justificativa_clinica": "..."
                }},
                "suplementacao_ergogenica": [
                    {{"suplemento": "...", "dosagem": "...", "justificativa_clinica": "..."}}
                ],
                "achados": [ {{"marcador": "...", "valor_encontrado": "...", "valor_referencia": "...", "status": "...", "analise_fisiologica": "..."}} ]
            }}
            """
            
        # PROMPT 3: MÓDULOS GERAIS
        elif modulo == "Microbiologia (Cultura e Antibiograma)":
            prompt = f"""
            Atue como um Médico Infectologista e Microbiologista Clínico de Elite.
            DADOS DO EXAME: {dados_extraidos}
            CONTEXTO CLÍNICO: {contexto_clinico}
            DIRETRIZES: {diretrizes}
            
            🚨 DIRETRIZ CLÍNICA E LABORATORIAL (MICROBIOLOGIA):
            O seu objetivo é analisar os resultados de culturas (urina, fezes, sangue, secreções) e os respetivos antibiogramas (MIC - Concentração Inibitória Mínima).
            1. Identifique claramente os microrganismos isolados (ou indique se a flora é normal/negativa).
            2. Cruze o resultado do antibiograma com as diretrizes de biosegurança e resistência antimicrobiana (ex: normas BrCAST/EUCAST/Fiocruz).
            3. Separe categoricamente os antibióticos aos quais a cepa é sensível e os que apresentam resistência.
            4. O 'conduta_infecciosa' deve sugerir a conduta farmacológica (antibioticoterapia empírica ou guiada) e as medidas de precaução (isolamento, etc).
            
            Retorne APENAS um formato JSON válido com as seguintes chaves ESTRITAS:
            {{
                "resumo_clinico": "Síntese infecciosa do resultado da cultura.",
                "bacterias_isoladas": ["Nome da bactéria 1 (UFC/ml se aplicável)", "se negativo, envie array vazio"],
                "antibioticos_sensiveis": ["Antibiótico A (MIC se houver)", "Antibiótico B", "se não houver, envie array vazio"],
                "antibioticos_resistentes": ["Antibiótico X", "Antibiótico Y", "se não houver, envie array vazio"],
                "conduta_infecciosa": "Sugestão de tratamento guiado, tempo de terapia ou necessidade de novos exames.",
                "achados": [
                    {{"marcador": "nome do exame/cultura", "valor_encontrado": "resultado", "valor_referencia": "referência", "status": "Alterado ou Normal", "analise_fisiologica": "análise microbiológica detalhada"}}
                ]
            }}
            """
        else:
            prompt = f"""
            Atue como um Médico Patologista e Clínico Geral experiente. Analise estes dados laboratoriais: {dados_extraidos}
            Contexto (Idade, Sexo, Peso e Condições): {contexto_clinico}
            Diretrizes: {diretrizes}
            Módulo selecionado: {modulo}
            
            Foque na interpretação médica diagnóstica ampla, não apenas nutricional.
            
            Retorne APENAS um formato JSON válido com as seguintes chaves:
            {{
                "resumo_clinico": "Resumo clínico adequado à patologia/fisiologia do paciente.",
                "achados": [
                    {{"marcador": "nome", "valor_encontrado": "valor", "valor_referencia": "ref", "status": "alterado ou normal", "analise_fisiologica": "análise médica/patológica", "diretriz_citada": "fontes"}}
                ],
                "radar_cientifico": "texto do radar ou vazio"
            }}
            """

        resposta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        # --- BLOCO DE SEGURANÇA PARA EXTRAIR O JSON ---
        if not resposta.text: return json.dumps({"erro": "A IA retornou uma resposta vazia."})
        
        json_match = re.search(r'\{.*\}', resposta.text, re.DOTALL)
        
        if json_match:
            json_puro = json_match.group(0)
        else:
            return json.dumps({
                "erro": "O modelo não retornou um formato JSON válido.",
                "resposta_bruta": resposta.text
            }, ensure_ascii=False)
        
        try:
            dados_ia = json.loads(json_puro)
        except Exception as e_json:
            return json.dumps({
                "erro": "A IA não retornou os dados no formato esperado.",
                "resposta_bruta": json_puro
            }, ensure_ascii=False)

        # Aplicador automático da sua biblioteca de Ranges Inteligentes
        if modulo in ["Fisiologia do Esporte e Alta Performance", "Performance, Emagrecimento e Endocrinologia", "Painel Completo (Bioquímica + Hematologia)"]:
            arquivo_ranges = 'ranges_alta_performance.json' if modulo == "Fisiologia do Esporte e Alta Performance" else 'ranges_longevidade.json'
            try:
                with open(arquivo_ranges, 'r', encoding='utf-8') as f:
                    ranges_dit = json.load(f)
                    
                if "achados" in dados_ia:
                    for achado in dados_ia["achados"]:
                        marcador = achado.get("marcador", "")
                        valor = achado.get("valor_encontrado", "")
                        novo_status = classificar_marcador_func(marcador, valor, ranges_dit, sexo)
                        if novo_status != "Análise Padrão": achado["status"] = novo_status
            except FileNotFoundError: pass

        return json.dumps(dados_ia, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"erro": f"Falha na comunicação com a API: {str(e)}"})


# --- CÉREBRO DE COMPARAÇÃO HISTÓRICA (Aba 1) ---
def gerar_comparativo_evolucao(historico_json):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return "Erro: Chave da API não encontrada."
        client = genai.Client(api_key=api_key)
        historico_texto = json.dumps(historico_json, ensure_ascii=False)
        prompt = f"""
        Atue como uma Junta Médica (Cardiologista, Endocrinologista e Nutricionista).
        Analise cronologicamente o seguinte histórico de exames laboratoriais do paciente:
        {historico_texto}
        
        Sua tarefa é redigir um "LAUDO RESUMIDO DE EVOLUÇÃO CLÍNICA" em Markdown.
        
        🚨 REGRAS DE FORMATAÇÃO ESTRITAS:
        O seu laudo DEVE ser estruturado OBRIGATORIAMENTE em torno dos 3 Eixos Metabólicos Fundamentais. Use estes exatos títulos:
        
        ### 🩸 Eixo Glicêmico e Resistência à Insulina
        (Descreva o que melhorou ou piorou na Glicose, HbA1c e HOMA-IR)
        
        ### ⚡ Eixo Hormonal e Anabolismo
        (Descreva o que melhorou ou piorou na Testosterona, Cortisol, Tireoide, etc.)
        
        ### 🫀 Eixo Inflamatório e Risco Cardiovascular
        (Descreva o que melhorou ou piorou nos Lipídios, LDL, Triglicerídeos, PCR, etc.)
        
        ### 🎯 Parecer Final da Junta Médica
        (Uma conclusão final e direta sobre o risco sistêmico atual e a eficácia da conduta até o momento.)
        """
        resposta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return resposta.text if resposta.text else "Não foi possível gerar a evolução."
    except Exception as e:
        return f"Erro ao gerar comparativo: {str(e)}"


# --- CÉREBRO DE SINCRONIZAÇÃO FAMILIAR (Aba 3) ---
def gerar_sincronizacao_familiar(nome_p1, historico_p1, nome_p2, historico_p2):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return json.dumps({"erro": "Chave da API não encontrada no arquivo .env."})
        client = genai.Client(api_key=api_key)
        laudo_p1 = historico_p1[-1]['laudo'] if historico_p1 else {}
        laudo_p2 = historico_p2[-1]['laudo'] if historico_p2 else {}
        prompt = f"""
        Atue como um Nutricionista Clínico e Esportivo de Elite. Crie uma base alimentar unificada para dois pacientes.
        PACIENTE 1: {nome_p1} | Estratégia: {json.dumps(laudo_p1.get('estrategia_nutricional', {}), ensure_ascii=False)} | Alertas: {json.dumps(laudo_p1.get('alertas_vermelhos', []) + laudo_p1.get('alertas_composicao', []), ensure_ascii=False)}
        PACIENTE 2: {nome_p2} | Estratégia: {json.dumps(laudo_p2.get('estrategia_nutricional', {}), ensure_ascii=False)} | Alertas: {json.dumps(laudo_p2.get('alertas_vermelhos', []) + laudo_p2.get('alertas_composicao', []), ensure_ascii=False)}
        Retorne APENAS JSON válido com chaves: "analise_conjunta", "lista_compras_base", "refeicoes_sincronizadas" (com refeicao, base_alimentar, porcao_p1, porcao_p2), "dica_preparo".
        """
        resposta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        resposta_texto = resposta.text
        try:
            match = re.search(r'\{.*\}', resposta_texto, re.DOTALL)
            json_puro = match.group(0) if match else resposta_texto
            json.loads(json_puro)
            return json_puro
        except: return json.dumps({"erro": "A IA não conseguiu estruturar a dieta."})
    except Exception as e: return json.dumps({"erro": f"Falha na comunicação: {str(e)}"})


# --- CÉREBRO DE PRESCRIÇÃO DE CARDÁPIO (Aba 5) ---
def gerar_cardapio_semanal(paciente, laudo_json, estrategia, restricoes):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return "Erro: Chave da API não encontrada."
        client = genai.Client(api_key=api_key)
        alertas = laudo_json.get('alertas_vermelhos', []) + laudo_json.get('alertas_composicao', [])
        macros = laudo_json.get('estrategia_nutricional', {})
        prompt = f"""
        Atue como um Nutricionista Clínico e Comportamental.
        Você vai elaborar um Cardápio Semanal (7 dias) realista para o paciente {paciente}.
        
        DADOS CLÍNICOS E METABÓLICOS:
        - Alertas: {alertas}
        - Alvo de Macros: {json.dumps(macros, ensure_ascii=False)}
        
        DIRETRIZ DA DIETA E PREFERÊNCIAS:
        - Linha escolhida: {estrategia}
        - Restrições: {restricoes}
        
        REGRAS DE ADESÃO E NUTRIÇÃO COMPORTAMENTAL (O FIM DO '8 OU 80'):
        1. É ESTRITAMENTE PROIBIDO cortar a 100% os alimentos culturais como arroz, macarrão, pão, batata ou tapioca, a menos que o paciente peça uma dieta "cetogênica". 
        2. O segredo clínico para tratar descontrole glicêmico (pré-diabetes) não é retirar o arroz, e sim CONTROLAR A PORÇÃO (ex: 2 a 3 colheres de sopa) e MISTURÁ-LO com muitas fibras (vegetais, feijão) e proteínas para baixar a carga glicêmica do prato.
        3. O paciente precisa olhar para o prato e ver "comida normal de verdade" (Tabela TACO). Se você prescrever apenas "peito de frango com brócolos e castanhas" em todas as refeições, o paciente vai abandonar a dieta em 3 dias. Seja criativo, prático e humano.
        4. Formate a resposta em Markdown puro, com os dias da semana e as refeições. 
        5. Coloque as quantidades em gramas e em medidas caseiras.
        """
        resposta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return resposta.text if resposta.text else "Não foi possível gerar o cardápio no momento."
    except Exception as e: return f"Erro ao gerar cardápio: {str(e)}"


# --- CÉREBRO DE VISÃO COMPUTACIONAL (MICROSCOPIA) ---
def analisar_lamina_microscopia(imagem_bytes, contexto, tipo_lamina):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return json.dumps({"erro": "Chave da API não encontrada."})
        client = genai.Client(api_key=api_key)
        
        # Converte os bytes da imagem para o formato legível pelo Gemini
        img = Image.open(io.BytesIO(imagem_bytes))
        
        prompt = f"""
        Atue como um Especialista Sênior em Biomedicina, Patologia e Microbiologia Clínica.
        Faça uma varredura rigorosa da imagem desta lâmina de microscópio que estou a enviar.
        
        Contexto do paciente: {contexto}
        Foco da Análise / Coloração esperada: {tipo_lamina}
        
        Descreva a morfologia celular, padrões de coloração (ex: Gram, Panótico), celularidade, presença de atipias (ex: anisocitose, poiquilocitose), desvios à esquerda ou presença de patógenos visíveis (ex: bacilos gram-negativos, cocos).
        
        Retorne APENAS um JSON estrito com esta estrutura:
        {{
            "qualidade_amostra": "Sua avaliação técnica da coloração e foco da lâmina.",
            "achados_morfologicos": [
                {{"estrutura": "Ex: Hemácia / Leucócito / Bactéria / Cristal", "descricao": "O detalhe morfológico observado na imagem."}}
            ],
            "hipotese_diagnostica": "Hipótese de bancada baseada no que você está a ver.",
            "alertas": ["Alerta crítico morfológico 1", "ou array vazio se estiver normal"]
        }}
        """
        
        # O Gemini recebe o texto E a imagem juntos
        resposta = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img]
        )
        match = re.search(r'\{.*\}', resposta.text, re.DOTALL)
        return match.group(0) if match else json.dumps({"erro": "A IA não retornou o formato estruturado."})
    except Exception as e:
        return json.dumps({"erro": f"Erro na análise da lâmina: {str(e)}"})
