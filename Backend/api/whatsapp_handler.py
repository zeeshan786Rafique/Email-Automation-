import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# Naya Helper Function: Number ko Twilio ke standard ke mutabiq theek karne ke liye
def format_phone_number(phone):
    phone = str(phone).strip()
    
    # Agar number '0' se shuru ho raha hai (e.g., 03091053298)
    if phone.startswith("0"):
        return "+92" + phone[1:]
    
    # Agar number '92' se shuru ho raha hai bina '+' ke (e.g., 923091053298)
    elif phone.startswith("92"):
        return "+" + phone
        
    # Agar pehle se theek hai (e.g., +923091053298)
    elif phone.startswith("+"):
        return phone
        
    # Default fallback
    return phone


def send_whatsapp_msg(to_number, message_body):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_whatsapp = os.getenv('TWILIO_WHATSAPP_NUMBER')

    client = Client(account_sid, auth_token)

    # 1. Pehle number ko theek karein
    formatted_number = format_phone_number(to_number)

    try:
        message = client.messages.create(
            from_=from_whatsapp,
            body=message_body,
            to=f'whatsapp:{formatted_number}'
        )
        print(f"✅ WhatsApp Sent Successfully to {formatted_number}! SID: {message.sid}")
        return True
    except Exception as e:
        print(f"❌ WhatsApp Error: {e}")
        return False