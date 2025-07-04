import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import psycopg2
from dotenv import load_dotenv
import json

# Carrega as variáveis de ambiente do arquivo .env (para ambiente local)
# No Render, elas são carregadas diretamente do painel de Environment Variables.
load_dotenv()

app = Flask(__name__)

# --- Configuração do Banco de Dados ---
DATABASE_URL = os.getenv('DATABASE_URL')

# Função para conectar ao DB e criar tabelas se não existirem
def get_db_connection():
    print("DEBUG: Tentando conectar ao banco de dados...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        print("INFO: Conexão com o banco de dados estabelecida com sucesso!")
        return conn
    except Exception as e:
        print(f"ERRO: Falha ao conectar ao banco de dados: {e}")
        return None

def create_tables():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Tabela para estados do usuário
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_states (
                    phone_number VARCHAR(20) PRIMARY KEY,
                    state VARCHAR(50) NOT NULL
                );
            """)
            # Tabela para dados da cotação
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    phone_number VARCHAR(20) PRIMARY KEY,
                    data JSONB NOT NULL DEFAULT '{}'::jsonb
                );
            """)
            print("INFO: Tabelas user_states e user_data verificadas/criadas no banco de dados.")
        except Exception as e:
            print(f"ERRO: Falha ao criar tabelas: {e}")
        finally:
            cursor.close()
            conn.close()
    else:
        print("ERRO: Não foi possível criar tabelas, conexão com DB falhou.")

# Chama a criação de tabelas ao iniciar a aplicação no Render
# Isso é executado uma vez quando o serviço é iniciado.
if DATABASE_URL:
    create_tables()
else:
    print("ATENÇÃO: DATABASE_URL não encontrada. Conexão ao DB será ignorada e tabelas não serão criadas automaticamente.")

# Função para obter o estado do usuário do DB
def get_user_state(phone_number):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT state FROM user_states WHERE phone_number = %s", (phone_number,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            print(f"DEBUG: Estado atual para {phone_number}: '{result[0]}' (do DB)")
            return result[0]
        print(f"DEBUG: Nenhum estado encontrado para {phone_number} no DB. Retornando None.")
        return None
    print(f"ERRO: Não foi possível obter estado para {phone_number}, conexão com DB falhou.")
    return None

# Função para salvar o estado do usuário no DB
def save_user_state(phone_number, state):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_states (phone_number, state) VALUES (%s, %s) ON CONFLICT (phone_number) DO UPDATE SET state = EXCLUDED.state",
            (phone_number, state)
        )
        cursor.close()
        conn.close()
        print(f"INFO: Estado '{state}' salvo para {phone_number} no DB.")
    else:
        print(f"ERRO: Não foi possível salvar estado '{state}' para {phone_number}, conexão com DB falhou.")

# Função para obter dados do usuário do DB
def get_user_data(phone_number):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM user_data WHERE phone_number = %s", (phone_number,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            data = result[0] if result[0] is not None else {}
            print(f"DEBUG: Dados atuais para {phone_number}: {data} (do DB)")
            return data
        print(f"DEBUG: Nenhum dado encontrado para {phone_number} no DB. Retornando vazio.")
        return {}
    print(f"ERRO: Não foi possível obter dados para {phone_number}, conexão com DB falhou.")
    return {}

# Função para salvar dados do usuário no DB
def save_user_data(phone_number, data):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        json_data = json.dumps(data)
        cursor.execute(
            "INSERT INTO user_data (phone_number, data) VALUES (%s, %s) ON CONFLICT (phone_number) DO UPDATE SET data = EXCLUDED.data",
            (phone_number, json_data)
        )
        cursor.close()
        conn.close()
        print(f"INFO: Dados '{data}' salvos para {phone_number} no DB.")
    else:
        print(f"ERRO: Não foi possível salvar dados '{data}' para {phone_number}, conexão com DB falhou.")

# --- Webhook do WhatsApp ---
@app.route("/webhook", methods=['POST'])
def whatsapp_webhook():
    print("\n--- Início do Processamento ---") # Log no início de cada requisição

    response = MessagingResponse()
    message_body = request.form['Body'].strip().lower()
    phone_number = request.form['From']

    user_state = get_user_state(phone_number)
    user_data = get_user_data(phone_number)

    # Lógica para reiniciar a conversa se a mensagem for 'olá' ou similar
    if message_body in ['oi', 'olá', 'menu', 'começar']:
        print("DEBUG: Detectada palavra-chave de reinício. Redefinindo estado e dados.")
        user_state = 'main_menu'
        user_data = {} # Limpa os dados da conversa anterior

    new_state = user_state
    response_message = ""

    # --- Lógica de Transição de Estados ---
    if user_state == 'main_menu' or user_state is None: # Adicionado 'user_state is None' para primeiro contato
        print(f"DEBUG: Entrou na lógica de 'main_menu'. Mensagem recebida: '{message_body}'")
        if message_body == '1':
            new_state = 'quotation_who'
            response_message = "Excelente! Para te ajudar a encontrar o plano ideal, preciso de algumas informações rápidas. Para quem seria o plano?\n\nPor favor, digite o número da opção desejada:\n\n1️⃣ *Para mim*\n\n2️⃣ *Para minha família*\n\n3️⃣ *Para minha empresa (PME)*"
            print(f"DEBUG: Transição de 'main_menu' para 'quotation_who'. Mensagem gerada: '{response_message[:50]}...'")
        elif message_body == '2':
            new_state = 'doubts_menu'
            response_message = "Para qual tipo de dúvida você precisa de ajuda?\n\n1️⃣ *Cobertura do plano*\n\n2️⃣ *Documentação necessária*\n\n3️⃣ *Valores e formas de pagamento*\n\n4️⃣ *Outros*"
            print(f"DEBUG: Transição de 'main_menu' para 'doubts_menu'. Mensagem gerada: '{response_message[:50]}...'")
        elif message_body == '3':
            new_state = 'support_menu'
            response_message = "Em que tipo de suporte posso te ajudar?\n\n1️⃣ *Alteração de plano existente*\n\n2️⃣ *Problemas com contratação*\n\n3️⃣ *Atendimento de sinistro*\n\n4️⃣ *Falar com um atendente*"
            print(f"DEBUG: Transição de 'main_menu' para 'support_menu'. Mensagem gerada: '{response_message[:50]}...'")
        elif message_body == '4':
            new_state = 'other_subject'
            response_message = "Por favor, descreva brevemente o assunto que você deseja tratar:"
            print(f"DEBUG: Transição de 'main_menu' para 'other_subject'. Mensagem gerada: '{response_message[:50]}...'")
        else:
            # Se for o primeiro contato ou opção inválida no menu principal
            if user_state is None: # Se o estado for None (primeiro contato)
                print("DEBUG: Primeiro contato. Definindo estado inicial 'main_menu'.")
            else: # Se o estado for 'main_menu' mas a opção inválida
                print(f"DEBUG: Opção inválida '{message_body}' no 'main_menu'.")
            
            new_state = 'main_menu' # Garante que volta para o menu principal
            response_message = "Olá! Sou o assistente virtual de Josildo Muniz, seu especialista em planos de saúde. Como posso te ajudar hoje?\n\nPor favor, digite o número da opção desejada:\n\n1️⃣ *Quero uma cotação*\n\n2️⃣ *Tenho dúvidas sobre um plano*\n\n3️⃣ *Preciso de suporte*\n\n4️⃣ *Outro assunto*"
            print(f"DEBUG: Mensagem de resposta para main_menu (opção inválida ou início): '{response_message[:50]}...'")
    
    elif user_state == 'quotation_who':
        print(f"DEBUG: Entrou na lógica de 'quotation_who'. Mensagem recebida: '{message_body}'")
        if message_body == '1':
            user_data['tipo_plano'] = 'individual'
            new_state = 'quotation_age'
            response_message = "Qual sua faixa de idade?\n\n1️⃣ *0 a 18 anos*\n\n2️⃣ *19 a 35 anos*\n\n3️⃣ *36 a 59 anos*\n\n4️⃣ *Acima de 60 anos*"
            print(f"DEBUG: Tipo de plano: individual. Transição para 'quotation_age'. Mensagem gerada: '{response_message[:50]}...'")
        elif message_body == '2':
            user_data['tipo_plano'] = 'familia'
            new_state = 'quotation_age'
            response_message = "Ótimo! Qual sua faixa de idade (ou da pessoa mais velha da família)?\n\nPor favor, digite o número da opção desejada:\n\n1️⃣ *0 a 18 anos*\n\n2️⃣ *19 a 35 anos*\n\n3️⃣ *36 a 59 anos*\n\n4️⃣ *Acima de 60 anos*"
            print(f"DEBUG: Tipo de plano: familia. Transição para 'quotation_age'. Mensagem gerada: '{response_message[:50]}...'")
        elif message_body == '3':
            user_data['tipo_plano'] = 'pme'
            new_state = 'quotation_pme_employees'
            response_message = "Entendido! Quantos beneficiários (vidas) sua empresa pretende incluir no plano?"
            print(f"DEBUG: Tipo de plano: pme. Transição para 'quotation_pme_employees'. Mensagem gerada: '{response_message[:50]}...'")
        else:
            response_message = "Opção inválida. Por favor, digite o número da opção desejada:\n\n1️⃣ *Para mim*\n\n2️⃣ *Para minha família*\n\n3️⃣ *Para minha empresa (PME)*"
            new_state = 'quotation_who' # Permanece no mesmo estado
            print(f"DEBUG: Opção inválida '{message_body}' em 'quotation_who'. Mensagem gerada: '{response_message[:50]}...'")

    elif user_state == 'quotation_age':
        print(f"DEBUG: Entrou na lógica de 'quotation_age'. Mensagem recebida: '{message_body}'")
        age_ranges = {
            '1': '0 a 18 anos',
            '2': '19 a 35 anos',
            '3': '36 a 59 anos',
            '4': 'Acima de 60 anos'
        }
        if message_body in age_ranges:
            user_data['faixa_idade'] = age_ranges[message_body]
            new_state = 'quotation_state' # Próximo estado, por exemplo
            response_message = "Certo! Em qual estado você reside?"
            print(f"DEBUG: Faixa de idade definida: {user_data['faixa_idade']}. Transição para 'quotation_state'. Mensagem gerada: '{response_message[:50]}...'")
        else:
            response_message = "Opção inválida. Por favor, digite o número da sua faixa de idade:\n\n1️⃣ *0 a 18 anos*\n\n2️⃣ *19 a 35 anos*\n\n3️⃣ *36 a 59 anos*\n\n4️⃣ *Acima de 60 anos*"
            new_state = 'quotation_age' # Permanece no mesmo estado
            print(f"DEBUG: Opção inválida '{message_body}' em 'quotation_age'. Mensagem gerada: '{response_message[:50]}...'")

    # --- Adicione mais 'elif user_state == 'SEU_PROXIMO_ESTADO':' aqui para continuar a lógica ---
    # Exemplo:
    # elif user_state == 'quotation_state':
    #    print(f"DEBUG: Entrou na lógica de 'quotation_state'. Mensagem recebida: '{message_body}'")
    #    user_data['estado'] = message_body.upper() # Salva o estado
    #    new_state = 'quotation_final' # Ou o próximo estado
    #    response_message = "Entendi. Para finalizar sua cotação, posso pegar seu nome completo e e-mail?"
    #    print(f"DEBUG: Estado salvo: {user_data['estado']}. Transição para 'quotation_final'. Mensagem gerada: '{response_message[:50]}...'")
    # else:
    #    response_message = "Desculpe, não entendi. Por favor, digite o nome do seu estado."
    #    new_state = 'quotation_state'

    else:
        # Lógica para estados não mapeados (pode ser útil para debugging)
        print(f"ERRO: Estado '{user_state}' não mapeado na lógica principal. Mensagem recebida: '{message_body}'")
        new_state = 'main_menu'
        response_message = "Desculpe, ocorreu um erro ou a conversa foi reiniciada. Por favor, digite 'olá' para começar novamente."


    # --- Salvando o novo estado e dados no DB ---
    save_user_state(phone_number, new_state)
    save_user_data(phone_number, user_data)
    
    # --- Construindo e Enviando a Resposta Twilio ---
    if not response_message:
        print("ERRO: response_message está vazio após processamento da lógica principal.")
        response_message = "Desculpe, ocorreu um erro inesperado. Por favor, digite 'olá' para recomeçar."
        new_state = 'main_menu' # Volta para o menu principal em caso de erro

    print(f"DEBUG: Mensagem final a ser enviada ({len(response_message)} caracteres): '{response_message[:100]}...'")
    
    response.message(response_message)
    print("--- Fim do Processamento ---")
    return str(response)

# --- Execução da Aplicação (Local vs. Render) ---
if __name__ == '__main__':
    # Este bloco só é executado quando você roda o script localmente (python main.py)
    # No Render, o Gunicorn é quem inicia a aplicação, não este if __name__ == '__main__':
    print("\n--- Rodando aplicação localmente ---")
    # Se você quiser testar a criação de tabelas localmente, pode descomentar a linha abaixo:
    # if DATABASE_URL:
    #     create_tables()
    app.run(debug=True) # debug=True ativa o modo de depuração para testes locais
