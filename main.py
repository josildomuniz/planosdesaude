import os
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

# --- Dicionário para armazenar o estado da conversa de cada usuário ---
# IMPORTANTE: Em um ambiente de produção real, você usaria um banco de dados (ex: SQLite, PostgreSQL)
# para persistir esses estados, pois um dicionário em memória será resetado se o servidor reiniciar.
user_states = {}
user_data = {} # Para armazenar os dados coletados de cada usuário

# --- Funções Auxiliares para os Textos dos Menus e Respostas ---

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

# --- Caminho 1: Quero uma cotação ---
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

# --- Caminho 2: Tenho dúvidas sobre um plano ---
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

# --- Caminho 3: Preciso de suporte ---
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

    current_state = user_states.get(sender_number, 'initial')
    print(f"Mensagem recebida de {sender_number}: '{incoming_msg}' (Estado Anterior: {current_state})")


    # --- 1. TRATAMENTO DE REINÍCIO OU FIM DE FLUXO ---
    # Esta é a condição mais importante e deve vir primeiro.
    # Se o usuário está iniciando a conversa, usando um comando de reinício,
    # ou se o fluxo anterior foi marcado como 'finished'.
    if incoming_msg in ["olá", "oi", "menu", "voltar", "iniciar"] or \
       current_state == 'initial' or \
       current_state == 'finished':
        
        user_states[sender_number] = 'main_menu'
        user_data[sender_number] = {} # Limpa dados anteriores para um novo fluxo
        msg.body(get_main_menu_text())
        print(f"Transição para: main_menu. Mensagem enviada: {get_main_menu_text()}")
        return str(resp) # ENCERRAR O PROCESSAMENTO AQUI para evitar lógica adicional.

    # --- 2. LÓGICA DO CHATBOT BASEADA NO ESTADO ATUAL ---
    # Cada 'elif' a seguir corresponde a um estado específico.

    # --- ESTADO: main_menu ---
    elif current_state == 'main_menu':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0 # Define como 0 para cair no else se não for um número

        if choice == 1: # Quero uma cotação
            user_states[sender_number] = 'quotation_who'
            msg.body(get_quotation_who_text())
            print(f"Transição para: quotation_who. Mensagem enviada: {get_quotation_who_text()}")
        elif choice == 2: # Tenho dúvidas sobre um plano
            user_states[sender_number] = 'doubt_type'
            msg.body(get_doubt_type_text())
            print(f"Transição para: doubt_type. Mensagem enviada: {get_doubt_type_text()}")
        elif choice == 3: # Preciso de suporte
            user_states[sender_number] = 'support_type'
            msg.body(get_support_type_text())
            print(f"Transição para: support_type. Mensagem enviada: {get_support_type_text()}")
        elif choice == 4: # Outro assunto
            user_states[sender_number] = 'other_subject_description'
            msg.body("Ok! Para que eu possa te direcionar, por favor, descreva brevemente o assunto no campo abaixo:")
            print(f"Transição para: other_subject_description. Mensagem enviada: 'Ok! Para que eu possa te direcionar...'")
        else: # Opção inválida para o menu principal
            msg.body(
                "Opção inválida. Por favor, digite '1', '2', '3' ou '4'.\n"
                "Você também pode digitar 'menu' a qualquer momento para voltar ao início."
            )
            print(f"Erro no main_menu. Mensagem enviada: 'Opção inválida...'")

    # --- Caminho 1: Cotação ---
    # --- ESTADO: quotation_who --- (Pergunta: Para quem seria o plano?)
    elif current_state == 'quotation_who':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice == 1: # Para mim
            user_data[sender_number]['tipo_plano'] = 'individual'
            user_states[sender_number] = 'quotation_age'
            msg.body(get_age_range_text())
            print(f"Transição para: quotation_age. Mensagem enviada: {get_age_range_text()}")
        elif choice == 2: # Para minha família
            user_data[sender_number]['tipo_plano'] = 'familia'
            user_states[sender_number] = 'quotation_age'
            msg.body(get_age_range_text())
            print(f"Transição para: quotation_age. Mensagem enviada: {get_age_range_text()}")
        elif choice == 3: # Para minha empresa (PME)
            user_data[sender_number]['tipo_plano'] = 'pme'
            user_states[sender_number] = 'quotation_pme_beneficiaries'
            msg.body(get_pme_beneficiaries_text())
            print(f"Transição para: quotation_pme_beneficiaries. Mensagem enviada: {get_pme_beneficiaries_text()}")
        else: # Opção inválida para quotation_who
            msg.body("Opção inválida. Por favor, digite '1' para *Para mim*, '2' para *Para minha família* ou '3' para *Para minha empresa (PME)*.")
            print(f"Erro no quotation_who. Mensagem enviada: 'Opção inválida...'")
    
    # --- ESTADO: quotation_age --- (Pergunta: Qual faixa de idade?)
    elif current_state == 'quotation_age':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice in [1, 2, 3, 4]:
            user_data[sender_number]['faixa_idade'] = incoming_msg
            user_states[sender_number] = 'quotation_region'
            msg.body(get_region_text())
            print(f"Transição para: quotation_region. Mensagem enviada: {get_region_text()}")
        else: # Opção inválida para quotation_age
            msg.body("Opção inválida. Por favor, digite 1, 2, 3 ou 4 para a faixa de idade.")
            print(f"Erro no quotation_age. Mensagem enviada: 'Opção inválida...'")
    
    # --- ESTADO: quotation_region --- (Pergunta: Região de atendimento?)
    elif current_state == 'quotation_region':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice in [1, 2]:
            user_data[sender_number]['regiao_atendimento'] = incoming_msg
            user_states[sender_number] = 'quotation_medical_dental'
            msg.body(get_medical_dental_text())
            print(f"Transição para: quotation_medical_dental. Mensagem enviada: {get_medical_dental_text()}")
        else: # Opção inválida para quotation_region
            msg.body("Opção inválida. Por favor, digite '1' para *Local* ou '2' para *Nacional*.")
            print(f"Erro no quotation_region. Mensagem enviada: 'Opção inválida...'")

    # --- ESTADO: quotation_medical_dental --- (Pergunta: Preferência por convênio?)
    elif current_state == 'quotation_medical_dental':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice in [1, 2, 3]:
            user_data[sender_number]['preferencia_convenio'] = incoming_msg
            user_states[sender_number] = 'quotation_collect_phone'
            msg.body("Para finalizarmos e Josildo te enviar as melhores opções, por favor, digite seu melhor telefone com DDD.")
            print(f"Transição para: quotation_collect_phone. Mensagem enviada: 'Para finalizarmos...'")
        else: # Opção inválida para quotation_medical_dental
            msg.body("Opção inválida. Por favor, digite '1' para *Médico*, '2' para *Odontológico* ou '3' para *Ambos*.")
            print(f"Erro no quotation_medical_dental. Mensagem enviada: 'Opção inválida...'")

    # --- ESTADO: quotation_collect_phone --- (Coleta de telefone e FINAL do fluxo Cotação Individual/Família)
    elif current_state == 'quotation_collect_phone':
        # Qualquer texto recebido aqui é considerado o telefone
        user_data[sender_number]['telefone_contato'] = incoming_msg
        print(f"Dados coletados para cotação individual/família de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos seus dados! Josildo vai analisar e entrar em contato em breve com as opções ideais para você. Obrigado!")
        user_states[sender_number] = 'finished' # Marca o fluxo como finalizado
        user_data[sender_number] = {} # Limpa os dados do usuário para o próximo fluxo
        print(f"Transição para: finished. Mensagem enviada: 'Recebemos seus dados! Josildo...'")

    # --- Fluxo PME (ramificação da Cotação) ---
    # --- ESTADO: quotation_pme_beneficiaries --- (Pergunta: Quantos beneficiários PME?)
    elif current_state == 'quotation_pme_beneficiaries':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice in [1, 2, 3]:
            user_data[sender_number]['num_beneficiarios_pme'] = incoming_msg
            user_states[sender_number] = 'quotation_pme_region'
            msg.body(get_pme_region_text())
            print(f"Transição para: quotation_pme_region. Mensagem enviada: {get_pme_region_text()}")
        else: # Opção inválida para quotation_pme_beneficiaries
            msg.body("Opção inválida. Por favor, digite 1, 2 ou 3 para o número de beneficiários.")
            print(f"Erro no quotation_pme_beneficiaries. Mensagem enviada: 'Opção inválida...'")

    # --- ESTADO: quotation_pme_region --- (Pergunta: Região de cobertura PME?)
    elif current_state == 'quotation_pme_region':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice in [1, 2]:
            user_data[sender_number]['regiao_pme'] = incoming_msg
            user_states[sender_number] = 'quotation_pme_collect_data'
            msg.body("Para Josildo te apresentar as melhores soluções empresariais, por favor, digite o CNPJ da empresa, seu nome e telefone com DDD.")
            print(f"Transição para: quotation_pme_collect_data. Mensagem enviada: 'Para Josildo te apresentar...'")
        else: # Opção inválida para quotation_pme_region
            msg.body("Opção inválida. Por favor, digite '1' para *Local* ou '2' para *Nacional*.")
            print(f"Erro no quotation_pme_region. Mensagem enviada: 'Opção inválida...'")

    # --- ESTADO: quotation_pme_collect_data --- (Coleta de dados PME e FINAL do fluxo Cotação PME)
    elif current_state == 'quotation_pme_collect_data':
        # Qualquer texto recebido aqui é considerado os dados PME
        user_data[sender_number]['dados_pme'] = incoming_msg
        print(f"Dados coletados para cotação PME de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos seus dados! Josildo entrará em contato para entender melhor as necessidades da sua empresa e apresentar as melhores propostas. Obrigado!")
        user_states[sender_number] = 'finished' # Marca o fluxo como finalizado
        user_data[sender_number] = {} # Limpa os dados
        print(f"Transição para: finished. Mensagem enviada: 'Recebemos seus dados! Josildo entrará...'")

    # --- Caminho 2: Dúvidas ---
    # --- ESTADO: doubt_type --- (Caminho 2: Qual tipo de dúvida?)
    elif current_state == 'doubt_type':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice == 1: # Cobertura do plano
            user_states[sender_number] = 'doubt_coverage_collect_plan'
            msg.body("Ok! Para te ajudar, preciso saber qual plano você tem em mente ou qual operadora.")
            print(f"Transição para: doubt_coverage_collect_plan. Mensagem enviada: 'Ok! Para te ajudar...'")
        elif choice == 2: # Reajuste/Valores
            user_states[sender_number] = 'doubt_readjustment_collect_plan'
            msg.body("Compreendo. Dúvidas sobre reajuste ou valores são comuns. Para te ajudar, por favor, digite o nome do seu plano e a operadora.")
            print(f"Transição para: doubt_readjustment_collect_plan. Mensagem enviada: 'Compreendo. Dúvidas sobre reajuste...'")
        elif choice == 3: # Carências
            user_states[sender_number] = 'doubt_care_seeking'
            msg.body(get_care_seeking_text())
            print(f"Transição para: doubt_care_seeking. Mensagem enviada: {get_care_seeking_text()}")
        elif choice == 4: # Como usar o plano
            user_states[sender_number] = 'doubt_how_to_use_collect_operator'
            msg.body("Entendido! Dúvidas sobre como usar o plano podem surgir. Qual o nome da sua operadora de saúde?")
            print(f"Transição para: doubt_how_to_use_collect_operator. Mensagem enviada: 'Entendido! Dúvidas sobre como usar...'")
        elif choice == 5: # Outra dúvida
            user_states[sender_number] = 'doubt_other_description'
            msg.body("Compreendo! Para que Josildo possa te ajudar com sua dúvida específica, por favor, descreva-a brevemente no campo abaixo:")
            print(f"Transição para: doubt_other_description. Mensagem enviada: 'Compreendo! Para que Josildo...'")
        else: # Opção inválida para doubt_type
            msg.body("Opção inválida. Por favor, digite 1, 2, 3, 4 ou 5 para o tipo de dúvida.")
            print(f"Erro no doubt_type. Mensagem enviada: 'Opção inválida...'")
    
    # --- ESTADO: doubt_coverage_collect_plan --- (Coleta de plano/operadora para dúvida de cobertura)
    elif current_state == 'doubt_coverage_collect_plan':
        user_data[sender_number]['plano_operadora_duvida_cobertura'] = incoming_msg
        user_states[sender_number] = 'doubt_coverage_collect_contact'
        msg.body("Entendido! Josildo é a pessoa ideal para esclarecer todas as coberturas. Por favor, digite seu nome e telefone com DDD para que ele entre em contato com você.")
        print(f"Transição para: doubt_coverage_collect_contact. Mensagem enviada: 'Entendido! Josildo é a pessoa ideal...'")
    
    # --- ESTADO: doubt_coverage_collect_contact --- (Coleta de contato e FINAL do fluxo Cobertura do plano)
    elif current_state == 'doubt_coverage_collect_contact':
        user_data[sender_number]['contato_duvida_cobertura'] = incoming_msg
        print(f"Dados coletados para dúvida de cobertura de {sender_number}: {user_data[sender_number]}")
        msg.body("Obrigado! Josildo entrará em contato para tirar suas dúvidas sobre a cobertura do plano.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Obrigado! Josildo entrará...'")
    
    # --- ESTADO: doubt_readjustment_collect_plan --- (Coleta de plano/operadora para dúvida de reajuste)
    elif current_state == 'doubt_readjustment_collect_plan':
        user_data[sender_number]['plano_operadora_reajuste'] = incoming_msg
        user_states[sender_number] = 'doubt_readjustment_collect_contact'
        msg.body("Ótimo! Para que Josildo te dê um suporte mais preciso, por favor, digite seu nome e telefone com DDD.")
        print(f"Transição para: doubt_readjustment_collect_contact. Mensagem enviada: 'Ótimo! Para que Josildo te dê...'")
    
    # --- ESTADO: doubt_readjustment_collect_contact --- (Coleta de contato e FINAL do fluxo Reajuste/Valores)
    elif current_state == 'doubt_readjustment_collect_contact':
        user_data[sender_number]['contato_reajuste'] = incoming_msg
        print(f"Dados coletados para dúvida de reajuste/valores de {sender_number}: {user_data[sender_number]}")
        msg.body("Certo! Josildo vai analisar sua questão sobre reajuste/valores e entrará em contato em breve.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Certo! Josildo vai analisar...'")

    # --- ESTADO: doubt_care_seeking --- (Pergunta: Já tem plano ou buscando?)
    elif current_state == 'doubt_care_seeking':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice in [1, 2]:
            user_data[sender_number]['car_seeking_type'] = incoming_msg
            user_states[sender_number] = 'doubt_care_collect_contact'
            msg.body("Perfeito! Para que Josildo possa te explicar tudo sobre carências, por favor, digite seu nome e telefone com DDD.")
            print(f"Transição para: doubt_care_collect_contact. Mensagem enviada: 'Perfeito! Para que Josildo...'")
        else: # Opção inválida para doubt_care_seeking
            msg.body("Opção inválida. Por favor, digite '1' para *Já tenho um plano* ou '2' para *Estou buscando um novo plano*.")
            print(f"Erro no doubt_care_seeking. Mensagem enviada: 'Opção inválida...'")
    
    # --- ESTADO: doubt_care_collect_contact --- (Coleta de contato e FINAL do fluxo Carências)
    elif current_state == 'doubt_care_collect_contact':
        user_data[sender_number]['contato_carencias'] = incoming_msg
        print(f"Dados coletados para dúvida de carências de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos seus dados! Josildo entrará em contato para detalhar as carências.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Recebemos seus dados! Josildo entrará...'")

    # --- ESTADO: doubt_how_to_use_collect_operator --- (Coleta de operadora para dúvida de como usar)
    elif current_state == 'doubt_how_to_use_collect_operator':
        user_data[sender_number]['operadora_como_usar'] = incoming_msg
        user_states[sender_number] = 'doubt_how_to_use_collect_contact'
        msg.body("Para te dar o melhor suporte, por favor, digite seu nome e telefone com DDD. Josildo vai te orientar.")
        print(f"Transição para: doubt_how_to_use_collect_contact. Mensagem enviada: 'Para te dar o melhor suporte...'")

    # --- ESTADO: doubt_how_to_use_collect_contact --- (Coleta de contato e FINAL do fluxo Como usar o plano)
    elif current_state == 'doubt_how_to_use_collect_contact':
        user_data[sender_number]['contato_como_usar'] = incoming_msg
        print(f"Dados coletados para dúvida de como usar o plano de {sender_number}: {user_data[sender_number]}")
        msg.body("Certo! Josildo vai te ajudar a entender como usar seu plano. Ele entrará em contato em breve.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Certo! Josildo vai te ajudar...'")

    # --- ESTADO: doubt_other_description --- (Coleta da descrição de "Outra dúvida")
    elif current_state == 'doubt_other_description':
        user_data[sender_number]['outra_duvida_descricao'] = incoming_msg
        user_states[sender_number] = 'doubt_other_collect_contact'
        msg.body("Obrigado! Para que Josildo possa te retornar, por favor, digite seu nome e telefone com DDD.")
        print(f"Transição para: doubt_other_collect_contact. Mensagem enviada: 'Obrigado! Para que Josildo...'")

    # --- ESTADO: doubt_other_collect_contact --- (Coleta de contato e FINAL do fluxo Outra dúvida)
    elif current_state == 'doubt_other_collect_contact':
        user_data[sender_number]['contato_outra_duvida'] = incoming_msg
        print(f"Dados coletados para outra dúvida de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos sua dúvida! Josildo entrará em contato para te ajudar.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Recebemos sua dúvida! Josildo...'")
        
    # --- Caminho 3: Suporte ---
    # --- ESTADO: support_type --- (Caminho 3: Qual tipo de suporte?)
    elif current_state == 'support_type':
        try:
            choice = int(incoming_msg)
        except ValueError:
            choice = 0

        if choice == 1: # Falar com Especialista
            user_states[sender_number] = 'support_specialist_collect_contact'
            msg.body("Certo! Alguém da equipe de Josildo entrará em contato. Para isso, por favor, digite seu nome e telefone com DDD.")
            print(f"Transição para: support_specialist_collect_contact. Mensagem enviada: 'Certo! Alguém da equipe...'")
        elif choice == 2: # Agendar reunião
            user_states[sender_number] = 'support_meeting_collect_data'
            msg.body("Ótimo! Para agendarmos sua reunião com Josildo, por favor, digite seu nome, telefone com DDD e o melhor período para você (manhã/tarde).")
            print(f"Transição para: support_meeting_collect_data. Mensagem enviada: 'Ótimo! Para agendarmos...'")
        elif choice == 3: # Problema com o boleto
            user_states[sender_number] = 'support_billing_description'
            msg.body("Entendido! Para te ajudar com o problema, por favor, descreva-o brevemente e digite seu nome e telefone com DDD.")
            print(f"Transição para: support_billing_description. Mensagem enviada: 'Entendido! Para te ajudar...'")
        else: # Opção inválida para support_type
            msg.body("Opção inválida. Por favor, digite 1, 2 ou 3 para o tipo de suporte.")
            print(f"Erro no support_type. Mensagem enviada: 'Opção inválida...'")

    # --- ESTADO: support_specialist_collect_contact --- (Coleta de contato e FINAL Falar com Especialista)
    elif current_state == 'support_specialist_collect_contact':
        user_data[sender_number]['contato_especialista'] = incoming_msg
        print(f"Dados coletados para falar com especialista de {sender_number}: {user_data[sender_number]}")
        msg.body("Entendido! Ligaremos assim que possível.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Entendido! Ligaremos...'")

    # --- ESTADO: support_meeting_collect_data --- (Coleta de dados e FINAL Agendar reunião)
    elif current_state == 'support_meeting_collect_data':
        user_data[sender_number]['dados_reuniao'] = incoming_msg
        print(f"Dados coletados para agendamento de reunião de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos sua solicitação! Josildo ou alguém da equipe entrará em contato para confirmar o agendamento.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Recebemos sua solicitação...'")

    # --- ESTADO: support_billing_description --- (Coleta de descrição e FINAL Problema com o boleto)
    elif current_state == 'support_billing_description':
        user_data[sender_number]['problema_boleto_descricao'] = incoming_msg
        print(f"Dados coletados para problema com boleto de {sender_number}: {user_data[sender_number]}")
        msg.body("Certo! Sua solicitação foi registrada e a equipe técnica irá verificar. Agradecemos a compreensão.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Certo! Sua solicitação...'")

    # --- Caminho 4: Outro Assunto ---
    # --- ESTADO: other_subject_description --- (Caminho 4: Coleta da descrição de "Outro assunto")
    elif current_state == 'other_subject_description':
        user_data[sender_number]['outro_assunto_descricao'] = incoming_msg
        user_states[sender_number] = 'other_subject_collect_contact'
        msg.body("Entendido! Para que Josildo ou a equipe adequada possa te ajudar, por favor, digite seu nome e telefone com DDD.")
        print(f"Transição para: other_subject_collect_contact. Mensagem enviada: 'Entendido! Para que Josildo...'")

    # --- ESTADO: other_subject_collect_contact --- (Coleta de contato e FINAL Outro assunto)
    elif current_state == 'other_subject_collect_contact':
        user_data[sender_number]['contato_outro_assunto'] = incoming_msg
        print(f"Dados coletados para outro assunto de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos sua mensagem! Em breve, alguém entrará em contato para te auxiliar com esse assunto.")
        user_states[sender_number] = 'finished'
        user_data[sender_number] = {}
        print(f"Transição para: finished. Mensagem enviada: 'Recebemos sua mensagem! Em breve...'")
        
    # --- 3. TRATAMENTO DE ENTRADAS NÃO RECONHECIDAS (Fallback) ---
    # Este 'else' só será alcançado se o 'current_state' não foi 'initial' ou 'finished'
    # e a 'incoming_msg' não se encaixou em nenhuma das condições para o 'current_state' específico.
    else:
        msg.body(
            "Desculpe, não entendi sua resposta para esta etapa da conversa. "
            "Por favor, digite uma opção válida ou 'menu' para voltar ao início."
        )
        print(f"Erro de fallback: '{incoming_msg}' no estado '{current_state}'. Mensagem enviada: 'Desculpe, não entendi...'")


    return str(resp)

# Para rodar localmente (não afeta o Render)
if __name__ == "__main__":
    print("Aplicativo Flask rodando localmente (se executado diretamente).")
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))