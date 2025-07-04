import os
import json
import psycopg2 # Importa a biblioteca para PostgreSQL
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

# Credenciais da Twilio carregadas das variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# URL do banco de dados PostgreSQL. O Render a injetará como uma variável de ambiente.
# Usamos 'DATABASE_URL' que é o padrão do Render para URLs de banco de dados.
DATABASE_URL = os.getenv("DATABASE_URL")

# Inicializa o cliente Twilio
try:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("INFO: Cliente Twilio inicializado com sucesso!")
    else:
        client = None
        print("ATENÇÃO: Credenciais da Twilio não configuradas. O cliente Twilio não será inicializado.")
except Exception as e:
    client = None
    print(f"ERRO: Falha ao inicializar o cliente Twilio: {e}")

# --- Funções para Interagir com o Banco de Dados ---

# Função para conectar ao banco de dados
def get_db_connection():
    try:
        # Verifica se DATABASE_URL está definido. Se não estiver, significa que estamos rodando localmente
        # e sem uma configuração de DB (ou usando um DB local, o que não é o foco agora).
        # Em produção no Render, DATABASE_URL SEMPRE estará presente.
        if not DATABASE_URL:
            print("ATENÇÃO: DATABASE_URL não encontrada. Conexão ao DB será ignorada.")
            return None
        
        # Conecta ao banco de dados usando a URL fornecida pelo Render
        conn = psycopg2.connect(DATABASE_URL)
        print("INFO: Conexão com o banco de dados estabelecida com sucesso!")
        return conn
    except Exception as e:
        print(f"ERRO: Falha ao conectar ao banco de dados: {e}")
        return None

# Função para inicializar a tabela de estados no DB, se ela não existir
def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Cria a tabela 'user_states' e 'user_data' se ainda não existirem
            # A coluna 'data' é TEXT, e armazenaremos JSON nela.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_states (
                    sender_number VARCHAR(255) PRIMARY KEY,
                    state VARCHAR(255) NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    sender_number VARCHAR(255) PRIMARY KEY,
                    data TEXT NOT NULL
                );
            """)
            conn.commit()
            print("INFO: Tabelas user_states e user_data verificadas/criadas no banco de dados.")
        except Exception as e:
            print(f"ERRO: Falha ao inicializar o banco de dados: {e}")
        finally:
            cur.close()
            conn.close()

# Função para carregar o estado de um usuário do DB
def load_user_state_from_db(sender_number):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT state FROM user_states WHERE sender_number = %s;", (sender_number,))
            result = cur.fetchone()
            return result[0] if result else 'initial'
        except Exception as e:
            print(f"ERRO: Falha ao carregar estado para {sender_number} do DB: {e}")
            return 'initial' # Retorna 'initial' em caso de erro
        finally:
            cur.close()
            conn.close()
    return 'initial' # Se não conseguir conectar ao DB, retorna 'initial'

# Função para salvar o estado de um usuário no DB
def save_user_state_to_db(sender_number, state):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_states (sender_number, state)
                VALUES (%s, %s)
                ON CONFLICT (sender_number) DO UPDATE SET state = EXCLUDED.state;
            """, (sender_number, state))
            conn.commit()
            print(f"INFO: Estado '{state}' salvo para {sender_number} no DB.")
        except Exception as e:
            print(f"ERRO: Falha ao salvar estado para {sender_number} no DB: {e}")
        finally:
            cur.close()
            conn.close()

# Função para carregar os dados de um usuário do DB
def load_user_data_from_db(sender_number):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT data FROM user_data WHERE sender_number = %s;", (sender_number,))
            result = cur.fetchone()
            return json.loads(result[0]) if result else {}
        except Exception as e:
            print(f"ERRO: Falha ao carregar dados para {sender_number} do DB: {e}")
            return {} # Retorna dicionário vazio em caso de erro
        finally:
            cur.close()
            conn.close()
    return {} # Se não conseguir conectar ao DB, retorna dicionário vazio

# Função para salvar os dados de um usuário no DB
def save_user_data_to_db(sender_number, data):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Converte o dicionário de dados para string JSON
            json_data = json.dumps(data)
            cur.execute("""
                INSERT INTO user_data (sender_number, data)
                VALUES (%s, %s)
                ON CONFLICT (sender_number) DO UPDATE SET data = EXCLUDED.data;
            """, (sender_number, json_data))
            conn.commit()
            print(f"INFO: Dados '{data}' salvos para {sender_number} no DB.")
        except Exception as e:
            print(f"ERRO: Falha ao salvar dados para {sender_number} no DB: {e}")
        finally:
            cur.close()
            conn.close()

# Inicializa o banco de dados (cria tabelas se não existirem) ao iniciar o app
init_db()

# --- Funções Auxiliares para os Textos dos Menus e Respostas (SEM MUDANÇAS AQUI) ---

def get_main_menu_text():
    return (
        "Olá! Sou o assistente virtual de Josildo Muniz, seu especialista em planos de saúde. "
        "Como posso te ajudar hoje?\n\n"
        "Por favor, digite o número da opção desejada:\n"
        "1️⃣ *Quero uma cotação*\n"
        "2️⃣ *Tenho dúvidas sobre um plano*\n"
        "3️⃣ *Preciso de suporte*\n"
        "4️⃣ *Outro assunto*"
    )

def get_quotation_who_text():
    return (
        "Excelente! Para te ajudar a encontrar o plano ideal, preciso de algumas informações rápidas. "
        "Para quem seria o plano?\n\n"
        "Por favor, digite o número da opção desejada:\n"
        "1️⃣ *Para mim*\n"
        "2️⃣ *Para minha família*\n"
        "3️⃣ *Para minha empresa (PME)*"
    )

def get_age_range_text():
    return (
        "Ótimo! Qual sua faixa de idade (ou da pessoa mais velha da família)?\n\n"
        "Por favor, digite o número da opção desejada:\n"
        "1️⃣ *0 a 18 anos*\n"
        "2️⃣ *19 a 35 anos*\n"
        "3️⃣ *36 a 59 anos*\n"
        "4️⃣ *Acima de 60 anos*"
    )

def get_region_text():
    return (
        "E para qual região você gostaria de atendimento?\n\n"
        "Por favor, digite o número da opção desejada:\n"
        "1️⃣ *Local (cidade/estado)*\n"
        "2️⃣ *Nacional*"
    )

def get_medical_dental_text():
    return (
        "Perfeito! Você tem alguma preferência por convênio médico ou odontológico?\n\n"
        "Por favor, digite o número da opção desejada:\n"
        "1️⃣ *Médico*\n"
        "2️⃣ *Odontológico*\n"
        "3️⃣ *Ambos*"
    )

def get_pme_beneficiaries_text():
    return (
        "Entendido! Para planos empresariais, preciso de alguns detalhes. "
        "Quantos beneficiários (funcionários e dependentes) a empresa teria?\n\n"
        "Por favor, digite o número da opção desejada:\n"
        "1️⃣ *2 a 29*\n"
        "2️⃣ *30 a 99*\n"
        "3️⃣ *100+*"
    )

def get_pme_region_text():
    return (
        "E qual a região de cobertura desejada para os colaboradores?\n\n"
        "Por favor, digite o número da opção desejada:\n"
        "1️⃣ *Local (cidade/estado)*\n"
        "2️⃣ *Nacional*"
    )

def get_doubt_type_text():
    return (
        "Certo! Qual tipo de dúvida você tem?\n\n"
        "1️⃣ *Cobertura do plano*\n"
        "2️⃣ *Reajuste/Valores*\n"
        "3️⃣ *Carências*\n"
        "4️⃣ *Como usar o plano*\n"
        "5️⃣ *Outra dúvida*"
    )

def get_care_seeking_text():
    return (
        "Entendido! Dúvidas sobre carências são muito importantes. "
        "Para te ajudar, você já tem um plano ou está buscando um novo?\n\n"
        "1️⃣ *Já tenho um plano*\n"
        "2️⃣ *Estou buscando um novo plano*"
    )

def get_support_type_text():
    return (
        "Olá! Para qual tipo de suporte você precisa de ajuda?\n\n"
        "1️⃣ *Falar com Especialista*\n"
        "2️⃣ *Agendar reunião*\n"
        "3️⃣ *Problema com o boleto*"
    )

# --- Função de Webhook ---
@app.route("/webhook", methods=['POST'])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').lower().strip()
    sender_number = request.values.get('From', '')

    resp = MessagingResponse()
    msg = resp.message()

    # Carrega o estado e dados do usuário específicos para esta requisição DO BANCO DE DADOS
    user_state = load_user_state_from_db(sender_number)
    user_data_dict = load_user_data_from_db(sender_number) # Carrega como dicionário
    
    current_state = user_state # O nome da variável é 'user_state' para o valor do estado

    print(f"\n--- Início do Processamento ---")
    print(f"Mensagem recebida de {sender_number}: '{incoming_msg}'")
    print(f"Estado atual para {sender_number}: '{current_state}' (do DB)")
    print(f"Dados atuais para {sender_number}: {user_data_dict} (do DB)")


    # Tenta converter a mensagem de entrada para inteiro APENAS SE for relevante
    try:
        incoming_choice_int = int(incoming_msg)
    except ValueError:
        incoming_choice_int = 0 # Valor padrão para "não é um número válido"

    # --- 1. Lógica para RETORNAR AO MENU PRINCIPAL ou INICIAR NOVA CONVERSA ---
    if incoming_msg in ["olá", "oi", "menu", "voltar", "iniciar"] or \
       current_state == 'initial' or \
       current_state == 'finished':
        
        current_state = 'main_menu' # Atualiza o estado
        user_data_dict = {} # Limpa os dados anteriores para um novo fluxo
        msg.body(get_main_menu_text())
        print(f"DEBUG: Reinício/Início de conversa. Novo estado: 'main_menu'. Mensagem enviada: {get_main_menu_text()}")
    
    # --- 2. Lógica de Navegação BASEADA NO ESTADO ATUAL ---
    elif current_state == 'main_menu':
        if incoming_choice_int == 1: # Quero uma cotação
            current_state = 'quotation_who'
            msg.body(get_quotation_who_text())
            print(f"DEBUG: Transição de 'main_menu' para 'quotation_who'. Mensagem enviada: {get_quotation_who_text()}")
        elif incoming_choice_int == 2: # Tenho dúvidas sobre um plano
            current_state = 'doubt_type'
            msg.body(get_doubt_type_text())
            print(f"DEBUG: Transição de 'main_menu' para 'doubt_type'. Mensagem enviada: {get_doubt_type_text()}")
        elif incoming_choice_int == 3: # Preciso de suporte
            current_state = 'support_type'
            msg.body(get_support_type_text())
            print(f"DEBUG: Transição de 'main_menu' para 'support_type'. Mensagem enviada: {get_support_type_text()}")
        elif incoming_choice_int == 4: # Outro assunto
            current_state = 'other_subject_description'
            msg.body("Ok! Para que eu possa te direcionar, por favor, descreva brevemente o assunto no campo abaixo:")
            print(f"DEBUG: Transição de 'main_menu' para 'other_subject_description'. Mensagem enviada: 'Ok! Para que eu possa te direcionar...'")
        else: # Opção inválida para o menu principal
            msg.body(
                "Opção inválida. Por favor, digite '1', '2', '3' ou '4'.\n"
                "Você também pode digitar 'menu' a qualquer momento para voltar ao início."
            )
            print(f"DEBUG: Entrada inválida em 'main_menu'. Mensagem enviada: 'Opção inválida...'")

    # --- Caminho 1: Cotação ---
    elif current_state == 'quotation_who':
        if incoming_choice_int == 1: # Para mim
            user_data_dict['tipo_plano'] = 'individual'
            current_state = 'quotation_age'
            msg.body(get_age_range_text())
            print(f"DEBUG: Transição de 'quotation_who' para 'quotation_age'. Mensagem enviada: {get_age_range_text()}")
        elif incoming_choice_int == 2: # Para minha família
            user_data_dict['tipo_plano'] = 'familia'
            current_state = 'quotation_age'
            msg.body(get_age_range_text())
            print(f"DEBUG: Transição de 'quotation_who' para 'quotation_age'. Mensagem enviada: {get_age_range_text()}")
        elif incoming_choice_int == 3: # Para minha empresa (PME)
            user_data_dict['tipo_plano'] = 'pme'
            current_state = 'quotation_pme_beneficiaries'
            msg.body(get_pme_beneficiaries_text())
            print(f"DEBUG: Transição de 'quotation_who' para 'quotation_pme_beneficiaries'. Mensagem enviada: {get_pme_beneficiaries_text()}")
        else:
            msg.body("Opção inválida. Por favor, digite '1' para *Para mim*, '2' para *Para minha família* ou '3' para *Para minha empresa (PME)*.")
            print(f"DEBUG: Entrada inválida em 'quotation_who'. Mensagem enviada: 'Opção inválida...'")
    
    elif current_state == 'quotation_age':
        if incoming_choice_int in [1, 2, 3, 4]:
            user_data_dict['faixa_idade'] = incoming_msg
            current_state = 'quotation_region'
            msg.body(get_region_text())
            print(f"DEBUG: Transição de 'quotation_age' para 'quotation_region'. Mensagem enviada: {get_region_text()}")
        else:
            msg.body("Opção inválida. Por favor, digite 1, 2, 3 ou 4 para a faixa de idade.")
            print(f"DEBUG: Entrada inválida em 'quotation_age'. Mensagem enviada: 'Opção inválida...'")
    
    elif current_state == 'quotation_region':
        if incoming_choice_int in [1, 2]:
            user_data_dict['regiao_atendimento'] = incoming_msg
            current_state = 'quotation_medical_dental'
            msg.body(get_medical_dental_text())
            print(f"DEBUG: Transição de 'quotation_region' para 'quotation_medical_dental'. Mensagem enviada: {get_medical_dental_text()}")
        else:
            msg.body("Opção inválida. Por favor, digite '1' para *Local* ou '2' para *Nacional*.")
            print(f"DEBUG: Entrada inválida em 'quotation_region'. Mensagem enviada: 'Opção inválida...'")

    elif current_state == 'quotation_medical_dental':
        if incoming_choice_int in [1, 2, 3]:
            user_data_dict['preferencia_convenio'] = incoming_msg
            current_state = 'quotation_collect_phone'
            msg.body("Para finalizarmos e Josildo te enviar as melhores opções, por favor, digite seu melhor telefone com DDD.")
            print(f"DEBUG: Transição de 'quotation_medical_dental' para 'quotation_collect_phone'. Mensagem enviada: 'Para finalizarmos...'")
        else:
            msg.body("Opção inválida. Por favor, digite '1' para *Médico*, '2' para *Odontológico* ou '3' para *Ambos*.")
            print(f"DEBUG: Entrada inválida em 'quotation_medical_dental'. Mensagem enviada: 'Opção inválida...'")

    elif current_state == 'quotation_collect_phone':
        user_data_dict['telefone_contato'] = incoming_msg
        print(f"DEBUG: Dados coletados para cotação individual/família de {sender_number}: {user_data_dict}")
        msg.body("Recebemos seus dados! Josildo vai analisar e entrar em contato em breve com as opções ideais para você. Obrigado!")
        current_state = 'finished'
        user_data_dict = {} # Limpa os dados do usuário para o próximo fluxo
        print(f"DEBUG: Fim do fluxo de cotação individual/família. Novo estado: 'finished'. Mensagem enviada: 'Recebemos seus dados! Josildo...'")

    # --- Fluxo PME (ramificação da Cotação) ---
    elif current_state == 'quotation_pme_beneficiaries':
        if incoming_choice_int in [1, 2, 3]:
            user_data_dict['num_beneficiarios_pme'] = incoming_msg
            current_state = 'quotation_pme_region'
            msg.body(get_pme_region_text())
            print(f"DEBUG: Transição de 'quotation_pme_beneficiaries' para 'quotation_pme_region'. Mensagem enviada: {get_pme_region_text()}")
        else:
            msg.body("Opção inválida. Por favor, digite 1, 2 ou 3 para o número de beneficiários.")
            print(f"DEBUG: Entrada inválida em 'quotation_pme_beneficiaries'. Mensagem enviada: 'Opção inválida...'")

    elif current_state == 'quotation_pme_region':
        if incoming_choice_int in [1, 2]:
            user_data_dict['regiao_pme'] = incoming_msg
            current_state = 'quotation_pme_collect_data'
            msg.body("Para Josildo te apresentar as melhores soluções empresariais, por favor, digite o CNPJ da empresa, seu nome e telefone com DDD.")
            print(f"DEBUG: Transição de 'quotation_pme_region' para 'quotation_pme_collect_data'. Mensagem enviada: 'Para Josildo te apresentar...'")
        else:
            msg.body("Opção inválida. Por favor, digite '1' para *Local* ou '2' para *Nacional*.")
            print(f"DEBUG: Entrada inválida em 'quotation_pme_region'. Mensagem enviada: 'Opção inválida...'")

    elif current_state == 'quotation_pme_collect_data':
        user_data_dict['dados_pme'] = incoming_msg
        print(f"DEBUG: Dados coletados para cotação PME de {sender_number}: {user_data_dict}")
        msg.body("Recebemos seus dados! Josildo entrará em contato para entender melhor as necessidades da sua empresa e apresentar as melhores propostas. Obrigado!")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de cotação PME. Novo estado: 'finished'. Mensagem enviada: 'Recebemos seus dados! Josildo entrará...'")

    # --- Caminho 2: Dúvidas ---
    elif current_state == 'doubt_type':
        if incoming_choice_int == 1: # Cobertura do plano
            current_state = 'doubt_coverage_collect_plan'
            msg.body("Ok! Para te ajudar, preciso saber qual plano você tem em mente ou qual operadora.")
            print(f"DEBUG: Transição de 'doubt_type' para 'doubt_coverage_collect_plan'. Mensagem enviada: 'Ok! Para te ajudar...'")
        elif incoming_choice_int == 2: # Reajuste/Valores
            current_state = 'doubt_readjustment_collect_plan'
            msg.body("Compreendo. Dúvidas sobre reajuste ou valores são comuns. Para te ajudar, por favor, digite o nome do seu plano e a operadora.")
            print(f"DEBUG: Transição de 'doubt_type' para 'doubt_readjustment_collect_plan'. Mensagem enviada: 'Compreendo. Dúvidas sobre reajuste...'")
        elif incoming_choice_int == 3: # Carências
            current_state = 'doubt_care_seeking'
            msg.body(get_care_seeking_text())
            print(f"DEBUG: Transição de 'doubt_type' para 'doubt_care_seeking'. Mensagem enviada: {get_care_seeking_text()}")
        elif incoming_choice_int == 4: # Como usar o plano
            current_state = 'doubt_how_to_use_collect_operator'
            msg.body("Entendido! Dúvidas sobre como usar o plano podem surgir. Qual o nome da sua operadora de saúde?")
            print(f"DEBUG: Transição de 'doubt_type' para 'doubt_how_to_use_collect_operator'. Mensagem enviada: 'Entendido! Dúvidas sobre como usar...'")
        elif incoming_choice_int == 5: # Outra dúvida
            current_state = 'doubt_other_description'
            msg.body("Compreendo! Para que Josildo possa te ajudar com sua dúvida específica, por favor, descreva-a brevemente no campo abaixo:")
            print(f"DEBUG: Transição de 'doubt_type' para 'doubt_other_description'. Mensagem enviada: 'Compreendo! Para que Josildo...'")
        else:
            msg.body("Opção inválida. Por favor, digite 1, 2, 3, 4 ou 5 para o tipo de dúvida.")
            print(f"DEBUG: Entrada inválida em 'doubt_type'. Mensagem enviada: 'Opção inválida...'")
    
    elif current_state == 'doubt_coverage_collect_plan':
        user_data_dict['plano_operadora_duvida_cobertura'] = incoming_msg
        current_state = 'doubt_coverage_collect_contact'
        msg.body("Entendido! Josildo é a pessoa ideal para esclarecer todas as coberturas. Por favor, digite seu nome e telefone com DDD para que ele entre em contato com você.")
        print(f"DEBUG: Transição de 'doubt_coverage_collect_plan' para 'doubt_coverage_collect_contact'. Mensagem enviada: 'Entendido! Josildo é a pessoa ideal...'")
    
    elif current_state == 'doubt_coverage_collect_contact':
        user_data_dict['contato_duvida_cobertura'] = incoming_msg
        print(f"DEBUG: Dados coletados para dúvida de cobertura de {sender_number}: {user_data_dict}")
        msg.body("Obrigado! Josildo entrará em contato para tirar suas dúvidas sobre a cobertura do plano.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de dúvida de cobertura. Novo estado: 'finished'. Mensagem enviada: 'Obrigado! Josildo entrará...'")
    
    elif current_state == 'doubt_readjustment_collect_plan':
        user_data_dict['plano_operadora_reajuste'] = incoming_msg
        current_state = 'doubt_readjustment_collect_contact'
        msg.body("Ótimo! Para que Josildo te dê um suporte mais preciso, por favor, digite seu nome e telefone com DDD.")
        print(f"DEBUG: Transição de 'doubt_readjustment_collect_plan' para 'doubt_readjustment_collect_contact'. Mensagem enviada: 'Ótimo! Para que Josildo te dê...'")
    
    elif current_state == 'doubt_readjustment_collect_contact':
        user_data_dict['contato_reajuste'] = incoming_msg
        print(f"DEBUG: Dados coletados para dúvida de reajuste/valores de {sender_number}: {user_data_dict}")
        msg.body("Certo! Josildo vai analisar sua questão sobre reajuste/valores e entrará em contato em breve.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de dúvida de reajuste. Novo estado: 'finished'. Mensagem enviada: 'Certo! Josildo vai analisar...'")

    elif current_state == 'doubt_care_seeking':
        if incoming_choice_int in [1, 2]:
            user_data_dict['car_seeking_type'] = incoming_msg
            current_state = 'doubt_care_collect_contact'
            msg.body("Perfeito! Para que Josildo possa te explicar tudo sobre carências, por favor, digite seu nome e telefone com DDD.")
            print(f"DEBUG: Transição de 'doubt_care_seeking' para 'doubt_care_collect_contact'. Mensagem enviada: 'Perfeito! Para que Josildo...'")
        else:
            msg.body("Opção inválida. Por favor, digite '1' para *Já tenho um plano* ou '2' para *Estou buscando um novo plano*.")
            print(f"DEBUG: Entrada inválida em 'doubt_care_seeking'. Mensagem enviada: 'Opção inválida...'")
    
    elif current_state == 'doubt_care_collect_contact':
        user_data_dict['contato_carencias'] = incoming_msg
        print(f"DEBUG: Dados coletados para dúvida de carências de {sender_number}: {user_data_dict}")
        msg.body("Recebemos seus dados! Josildo entrará em contato para detalhar as carências.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de dúvida de carências. Novo estado: 'finished'. Mensagem enviada: 'Recebemos seus dados! Josildo entrará...'")

    elif current_state == 'doubt_how_to_use_collect_operator':
        user_data_dict['operadora_como_usar'] = incoming_msg
        current_state = 'doubt_how_to_use_collect_contact'
        msg.body("Para te dar o melhor suporte, por favor, digite seu nome e telefone com DDD. Josildo vai te orientar.")
        print(f"DEBUG: Transição de 'doubt_how_to_use_collect_operator' para 'doubt_how_to_use_collect_contact'. Mensagem enviada: 'Para te dar o melhor suporte...'")

    elif current_state == 'doubt_how_to_use_collect_contact':
        user_data_dict['contato_como_usar'] = incoming_msg
        print(f"DEBUG: Dados coletados para dúvida de como usar o plano de {sender_number}: {user_data_dict}")
        msg.body("Certo! Josildo vai te ajudar a entender como usar seu plano. Ele entrará em contato em breve.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de como usar o plano. Novo estado: 'finished'. Mensagem enviada: 'Certo! Josildo vai te ajudar...'")

    elif current_state == 'doubt_other_description':
        user_data_dict['outra_duvida_descricao'] = incoming_msg
        current_state = 'doubt_other_collect_contact'
        msg.body("Obrigado! Para que Josildo possa te retornar, por favor, digite seu nome e telefone com DDD.")
        print(f"DEBUG: Transição de 'doubt_other_description' para 'doubt_other_collect_contact'. Mensagem enviada: 'Obrigado! Para que Josildo...'")

    elif current_state == 'doubt_other_collect_contact':
        user_data_dict['contato_outra_duvida'] = incoming_msg
        print(f"DEBUG: Dados coletados para outra dúvida de {sender_number}: {user_data_dict}")
        msg.body("Recebemos sua dúvida! Josildo entrará em contato para te ajudar.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de outra dúvida. Novo estado: 'finished'. Mensagem enviada: 'Recebemos sua dúvida! Josildo entrará...'")
        
    # --- Caminho 3: Suporte ---
    elif current_state == 'support_type':
        if incoming_choice_int == 1: # Falar com Especialista
            current_state = 'support_specialist_collect_contact'
            msg.body("Certo! Alguém da equipe de Josildo entrará em contato. Para isso, por favor, digite seu nome e telefone com DDD.")
            print(f"DEBUG: Transição de 'support_type' para 'support_specialist_collect_contact'. Mensagem enviada: 'Certo! Alguém da equipe...'")
        elif incoming_choice_int == 2: # Agendar reunião
            current_state = 'support_meeting_collect_data'
            msg.body("Ótimo! Para agendarmos sua reunião com Josildo, por favor, digite seu nome, telefone com DDD e o melhor período para você (manhã/tarde).")
            print(f"DEBUG: Transição de 'support_type' para 'support_meeting_collect_data'. Mensagem enviada: 'Ótimo! Para agendarmos...'")
        elif incoming_choice_int == 3: # Problema com o boleto
            current_state = 'support_billing_description'
            msg.body("Entendido! Para te ajudar com o problema, por favor, descreva-o brevemente e digite seu nome e telefone com DDD.")
            print(f"DEBUG: Transição de 'support_type' para 'support_billing_description'. Mensagem enviada: 'Entendido! Para te ajudar...'")
        else:
            msg.body("Opção inválida. Por favor, digite 1, 2 ou 3 para o tipo de suporte.")
            print(f"DEBUG: Entrada inválida em 'support_type'. Mensagem enviada: 'Opção inválida...'")

    elif current_state == 'support_specialist_collect_contact':
        user_data_dict['contato_especialista'] = incoming_msg
        print(f"DEBUG: Dados coletados para falar com especialista de {sender_number}: {user_data_dict}")
        msg.body("Entendido! Ligaremos assim que possível.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de falar com especialista. Novo estado: 'finished'. Mensagem enviada: 'Entendido! Ligaremos...'")

    elif current_state == 'support_meeting_collect_data':
        user_data_dict['dados_reuniao'] = incoming_msg
        print(f"DEBUG: Dados coletados para agendamento de reunião de {sender_number}: {user_data_dict}")
        msg.body("Recebemos sua solicitação! Josildo ou alguém da equipe entrará em contato para confirmar o agendamento.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de agendar reunião. Novo estado: 'finished'. Mensagem enviada: 'Recebemos sua solicitação...'")

    elif current_state == 'support_billing_description':
        user_data_dict['problema_boleto_descricao'] = incoming_msg
        print(f"DEBUG: Dados coletados para problema com boleto de {sender_number}: {user_data_dict}")
        msg.body("Certo! Sua solicitação foi registrada e a equipe técnica irá verificar. Agradecemos a compreensão.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de problema com boleto. Novo estado: 'finished'. Mensagem enviada: 'Certo! Sua solicitação...'")

    # --- Caminho 4: Outro Assunto ---
    elif current_state == 'other_subject_description':
        user_data_dict['outro_assunto_descricao'] = incoming_msg
        current_state = 'other_subject_collect_contact'
        msg.body("Entendido! Para que Josildo ou a equipe adequada possa te ajudar, por favor, digite seu nome e telefone com DDD.")
        print(f"DEBUG: Transição de 'other_subject_description' para 'other_subject_collect_contact'. Mensagem enviada: 'Entendido! Para que Josildo...'")

    elif current_state == 'other_subject_collect_contact':
        user_data_dict['contato_outro_assunto'] = incoming_msg
        print(f"DEBUG: Dados coletados para outro assunto de {sender_number}: {user_data_dict}")
        msg.body("Recebemos sua mensagem! Em breve, alguém entrará em contato para te auxiliar com esse assunto.")
        current_state = 'finished'
        user_data_dict = {}
        print(f"DEBUG: Fim do fluxo de outro assunto. Novo estado: 'finished'. Mensagem enviada: 'Recebemos sua mensagem! Em breve...'")
        
    # --- 3. TRATAMENTO DE ENTRADAS NÃO RECONHECIDAS (Fallback) ---
    else:
        msg.body(
            "Desculpe, não entendi sua resposta para esta etapa da conversa. "
            "Por favor, digite uma opção válida ou 'menu' para voltar ao início."
        )
        print(f"DEBUG: Fallback - Entrada inválida: '{incoming_msg}' no estado '{current_state}'. Mensagem enviada: 'Desculpe, não entendi...'")
    
    # --- SALVA OS ESTADOS E DADOS NO BANCO DE DADOS APÓS CADA REQUISIÇÃO ---
    save_user_state_to_db(sender_number, current_state)
    save_user_data_to_db(sender_number, user_data_dict)
    
    print(f"--- Fim do Processamento ---")
    return str(resp)

# Para rodar localmente (não afeta o Render)
if __name__ == "__main__":
    print("Aplicativo Flask rodando localmente (se executado diretamente).")
    # Ao rodar localmente, você pode definir DATABASE_URL em seu .env para testar a conexão com o DB
    # Ex: DATABASE_URL="postgresql://seu_usuario:sua_senha@localhost:5432/seu_banco"
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))
    