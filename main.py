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

# --- Funções Auxiliares (Opcional, para organizar respostas) ---
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


@app.route("/webhook", methods=['POST'])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').lower().strip() # .strip() para remover espaços extras
    sender_number = request.values.get('From', '')

    resp = MessagingResponse()
    msg = resp.message()

    print(f"Mensagem recebida de {sender_number}: '{incoming_msg}' (Estado: {user_states.get(sender_number, 'Nenhum')})")

    # --- Lógica Principal do Chatbot baseada no estado da conversa ---

    current_state = user_states.get(sender_number, 'initial') # Pega o estado atual do usuário ou 'initial'

    # --- Início da Conversa / Menu Principal ---
    if current_state == 'initial' or incoming_msg in ["olá", "oi", "menu", "voltar"]:
        user_states[sender_number] = 'main_menu'
        user_data[sender_number] = {} # Limpa dados anteriores ao iniciar um novo fluxo
        msg.body(get_main_menu_text())

    # --- Caminho 1: Quero uma cotação ---
    elif current_state == 'main_menu' and incoming_msg == '1':
        user_states[sender_number] = 'quotation_who'
        msg.body(get_quotation_who_text())

    # --- Caminho 1.1: Para mim / Para minha família ---
    elif current_state == 'quotation_who' and incoming_msg in ['1', '2']:
        user_data[sender_number]['tipo_plano'] = 'individual_familia' if incoming_msg == '1' else 'familia'
        user_states[sender_number] = 'quotation_age'
        msg.body(get_age_range_text())

    elif current_state == 'quotation_age':
        user_data[sender_number]['faixa_idade'] = incoming_msg
        user_states[sender_number] = 'quotation_region'
        msg.body(get_region_text())

    elif current_state == 'quotation_region':
        user_data[sender_number]['regiao_atendimento'] = incoming_msg
        user_states[sender_number] = 'quotation_medical_dental'
        msg.body(get_medical_dental_text())
    
    elif current_state == 'quotation_medical_dental':
        user_data[sender_number]['preferencia_convenio'] = incoming_msg
        user_states[sender_number] = 'quotation_collect_phone'
        msg.body("Para finalizarmos e Josildo te enviar as melhores opções, por favor, digite seu melhor telefone com DDD.")

    elif current_state == 'quotation_collect_phone':
        user_data[sender_number]['telefone_contato'] = incoming_msg
        # --- FINAL DO FLUXO DE COTAÇÃO INDIVIDUAL/FAMÍLIA ---
        # Aqui você pode enviar os dados para um e-mail, planilha, CRM, etc.
        print(f"Dados coletados para cotação individual/família de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos seus dados! Josildo vai analisar e entrar em contato em breve com as opções ideais para você. Obrigado!")
        user_states[sender_number] = 'finished' # Marca o fluxo como finalizado

    # --- Caminho 1.2: Para minha empresa (PME) ---
    elif current_state == 'quotation_who' and incoming_msg == '3':
        user_data[sender_number]['tipo_plano'] = 'pme'
        user_states[sender_number] = 'quotation_pme_beneficiaries'
        msg.body(get_pme_beneficiaries_text())

    elif current_state == 'quotation_pme_beneficiaries':
        user_data[sender_number]['num_beneficiarios_pme'] = incoming_msg
        user_states[sender_number] = 'quotation_pme_region'
        msg.body(get_pme_region_text())

    elif current_state == 'quotation_pme_region':
        user_data[sender_number]['regiao_pme'] = incoming_msg
        user_states[sender_number] = 'quotation_pme_collect_data'
        msg.body("Para Josildo te apresentar as melhores soluções empresariais, por favor, digite o CNPJ da empresa, seu nome e telefone com DDD.")

    elif current_state == 'quotation_pme_collect_data':
        user_data[sender_number]['dados_pme'] = incoming_msg # Coleta CNPJ, nome e telefone em uma única string
        # --- FINAL DO FLUXO DE COTAÇÃO PME ---
        # Aqui você pode enviar os dados para um e-mail, planilha, CRM, etc.
        print(f"Dados coletados para cotação PME de {sender_number}: {user_data[sender_number]}")
        msg.body("Recebemos seus dados! Josildo entrará em contato para entender melhor as necessidades da sua empresa e apresentar as melhores propostas. Obrigado!")
        user_states[sender_number] = 'finished' # Marca o fluxo como finalizado

    # --- Caminho 2: Tenho dúvidas sobre um plano (Esqueleto) ---
    elif current_state == 'main_menu' and incoming_msg == '2':
        user_states[sender_number] = 'doubt_type'
        msg.body(
            "Certo! Qual tipo de dúvida você tem?\n\n"
            "1️⃣ *Cobertura do plano*\n"
            "2️⃣ *Reajuste/Valores*\n"
            "3️⃣ *Carências*\n"
            "4️⃣ *Como usar o plano*\n"
            "5️⃣ *Outra dúvida*"
        )
    elif current_state == 'doubt_type':
        if incoming_msg == '1':
            user_states[sender_number] = 'doubt_coverage_collect_plan'
            msg.body("Ok! Para te ajudar, preciso saber qual plano você tem em mente ou qual operadora.")
        # ... Adicione mais 'elif' para as outras opções de dúvida (2, 3, 4, 5)
        # Exemplo para 'Cobertura do plano':
        elif current_state == 'doubt_coverage_collect_plan':
            user_data[sender_number]['plano_operadora_duvida_cobertura'] = incoming_msg
            user_states[sender_number] = 'doubt_coverage_collect_contact'
            msg.body("Entendido! Josildo é a pessoa ideal para esclarecer todas as coberturas. Por favor, digite seu nome e telefone com DDD para que ele entre em contato com você.")
        elif current_state == 'doubt_coverage_collect_contact':
            user_data[sender_number]['contato_duvida_cobertura'] = incoming_msg
            print(f"Dados coletados para dúvida de cobertura de {sender_number}: {user_data[sender_number]}")
            msg.body("Obrigado! Josildo entrará em contato para tirar suas dúvidas sobre a cobertura do plano.")
            user_states[sender_number] = 'finished'
        # ... e assim por diante para os outros sub-caminhos de dúvida.
        else:
            msg.body("Opção inválida. Por favor, digite 1, 2, 3, 4 ou 5 para o tipo de dúvida.")
            user_states[sender_number] = 'doubt_type' # Volta para o mesmo estado para tentar novamente

    # --- Caminho 3: Preciso de suporte (Esqueleto) ---
    elif current_state == 'main_menu' and incoming_msg == '3':
        user_states[sender_number] = 'support_type'
        msg.body(
            "Olá! Para qual tipo de suporte você precisa de ajuda?\n\n"
            "1️⃣ *Falar com Especialista*\n"
            "2️⃣ *Agendar reunião*\n"
            "3️⃣ *Problema com o boleto*"
        )
    # ... Adicione a lógica para os sub-caminhos de suporte (3.1, 3.2, 3.3)

    # --- Caminho 4: Outro assunto (Esqueleto) ---
    elif current_state == 'main_menu' and incoming_msg == '4':
        user_states[sender_number] = 'other_subject_description'
        msg.body("Ok! Para que eu possa te direcionar, por favor, descreva brevemente o assunto no campo abaixo:")
    # ... Adicione a lógica para coletar a descrição e os dados de contato

    # --- Mensagem padrão para entradas não reconhecidas em um estado específico ---
    else:
        # Se o usuário está em um fluxo, mas a resposta não corresponde ao esperado
        if current_state not in ['initial', 'main_menu', 'finished']:
            msg.body(
                "Desculpe, não entendi sua resposta para esta etapa. "
                "Por favor, tente novamente ou digite 'menu' para voltar ao início."
            )
        else: # Se o usuário não está em nenhum fluxo ou digitou algo aleatório no menu principal
            msg.body("Desculpe, não entendi. Por favor, digite 'Olá' ou 'menu' para ver as opções principais.")
            user_states[sender_number] = 'main_menu'


    return str(resp)

# Para rodar localmente (não afeta o Render)
if __name__ == "__main__":
    print("Aplicativo Flask rodando localmente (se executado diretamente).")
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))