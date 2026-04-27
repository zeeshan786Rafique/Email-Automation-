from whatsapp_handler import send_whatsapp_msg
import os
from dotenv import load_dotenv

load_dotenv()

# Apna number verify karne ke liye
my_number = "+923091053298" 
msg = "🔥 *Phase 6 Success!*\n\nShani Bhai, aapka Email Automation system ab WhatsApp se connect ho gaya hai. Congratulations!"

if send_whatsapp_msg(my_number, msg):
    print("🚀 Test Successful! Check your WhatsApp.")
else:
    print("❌ Test Failed. Check your credentials.")