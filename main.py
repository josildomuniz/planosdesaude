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
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER") # Seu número do sandbox ou aprovado, ex: whatsapp:+14155238886

# Inicializa o cliente Twilio
try:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("INFO: Cliente Twilio inicializado com sucesso!")
    else:
        client = None # Define como None se as credenciais não estiverem presentes
        print("ATENÇÃO: Credenciais da Twilio não configuradas. O cliente Twilio não será inicializado.")
except Exception as e:
    client = None
    print(f"ERRO: Falha ao inicializar o cliente Twilio: {e}")


# Função para enviar mensagens (usada se precisar iniciar conversa ou enviar algo fora do webhook)
def send_whatsapp_message(to_number, message_body):
    if client and TWILIO_WHATSAPP_NUMBER:
        try:
            message = client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=message_body,
                to=to_number
            )
            print(f"Mensagem enviada para {to_number}: {message_body}")
            return True
        except Exception as e:
            print(f"Erro ao enviar mensagem para {to_number}: {e}")
            return False
    else:
        print("Erro: Credenciais Twilio ou número do WhatsApp não configurados para enviar mensagens.")
        return False

@app.route("/webhook", methods=['POST'])
def whatsapp_webhook():
    # Recebe a mensagem do WhatsApp
    incoming_msg = request.values.get('Body', '').lower()
    sender_number = request.values.get('From', '')

    resp = MessagingResponse()
    msg = resp.message()

    print(f"Mensagem recebida de {sender_number}: {incoming_msg}")

    # Lógica do chatbot
    if "olá" in incoming_msg or "oi" in incoming_msg:
        msg.body("Olá! Sou o assistente de planos de saúde. Como posso ajudar hoje?")
    elif "planos" in incoming_msg:
        msg.body("Oferecemos planos de saúde individuais, familiares e empresariais. Qual tipo te interessa?")
    elif "cotacao" in incoming_msg or "precos" in incoming_msg:
        msg.body("Para uma cotação, preciso de algumas informações: idade dos beneficiários, CEP e se possuem alguma doença preexistente. Podemos continuar por aqui ou prefere falar com um consultor?")
    elif "consultor" in incoming_msg or "falar com alguem" in incoming_msg:
        msg.body("Claro! Posso conectar você a um consultor. Por favor, confirme seu nome e telefone para contato.")
    elif "obrigado" in incoming_msg or "valeu" in incoming_msg:
        msg.body("De nada! Se precisar de mais alguma coisa, é só chamar.")
    else:
        msg.body("Desculpe, não entendi. Posso ajudar com informações sobre planos, cotação ou conectar você a um consultor.")

    return str(resp)

# Para rodar localmente, se necessário (não será usado no Render diretamente)
if __name__ == "__main__":
    # Em ambiente de produção (Render), gunicorn irá iniciar o app.
    # Esta parte é mais para teste local.
    # Certifique-se de que o .env está configurado localmente se for testar.
    print("Aplicativo Flask rodando localmente (se executado diretamente).")
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))