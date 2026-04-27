from groq import Groq
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
from whatsapp_handler import send_whatsapp_msg

# ==========================================
# 1. CONFIGURATION & SETUP
# Ye hissa environment variables aur API keys load karta hai.
# ==========================================
load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "shaniizr786rafique@gmail.com"
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq Client setup
groq_client = Groq(api_key=GROQ_API_KEY)

# Google Sheets setup
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    gs_client = gspread.authorize(creds)
    sheet = gs_client.open("Email Automation with python").sheet1
    print("✅ Google Sheets connected successfully!")
except Exception as e:
    print(f"❌ Sheets Connection Error: {e}")


# ==========================================
# 2. UTILITY FUNCTIONS (Aapke Asli Hathyaar)
# ==========================================

# Maqsad: Groq AI ko use karke check karna ke user ka reply Positive (Hot) hai ya Negative (Cold).
# Agar "Hot Lead" ho, to foran Admin aur User dono ko WhatsApp notification bhejna.
def analyze_sentiment(reply_text, user_name, user_phone):
    if not reply_text.strip():
        return "Replied"

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a lead classifier. Only answer with exactly one of these three phrases: 'Hot Lead', 'Cold Lead', or 'Follow-up'."
                },
                {
                    "role": "user",
                    "content": f"Classify this email: {reply_text}"
                }
            ],
            model="llama-3.1-8b-instant", 
            temperature=0.1,
        )
        
        if chat_completion.choices:
            category = chat_completion.choices[0].message.content.strip()
            # Safai: Faltu symbols hata dena
            category = category.replace("*", "").replace("'", "").replace('"', '').replace(".", "")
            print(f"✅ AI SUCCESS (Groq): {category}")
            
            # Agar AI ne Hot Lead kaha hai, to WhatsApp bhejien
            if "Hot Lead" in category:
                # 1. Admin (Aapko) notification bhejien
                send_whatsapp_msg("+923091053298", f"📢 *New Hot Lead!*\nUser: {user_name}\nReply: {reply_text}")
                
                # 2. User ko greeting bhejien
                if user_phone:
                    send_whatsapp_msg(user_phone, "Thank you for your interest! We will contact you soon.")
            
            return category
            
    except Exception as e:
        print(f"❌ Groq API Error: {e}")
        return "Replied"


# Maqsad: Jo email aayi hai, usme se sirf asli message nikalna (Pichli history aur faltu text ko filter karna).
def get_email_body(msg):
    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        
        clean_body = body.split("On Sun, Apr")[0].split("-----Original Message-----")[0].strip()
        return clean_body
    except Exception as e:
        print(f"❌ Body Extraction Error: {e}")
        return ""


# Maqsad: Naye aane wale user ko welcome email bhejna.
def send_welcome_email(to_email, user_name):
    try:
        message = MIMEMultipart()
        message["From"] = SENDER_EMAIL
        message["To"] = to_email
        message["Subject"] = "Welcome to Our Platform! 🚀"
        body = f"Hi {user_name},\n\nAapka registration successful ho gaya hai. Hum jald raabta karenge!"
        message.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(message)
        server.quit()
        print(f"🚀 Email delivered to {to_email}")
    except Exception as e:
        print(f"❌ SMTP Error: {e}")


# Maqsad: Har 1 minute baad Inbox check karna ke kisi user ka reply aaya hai ya nahi. 
# Agar aaya hai, to AI se classify karwa ke Google Sheet update karna.
def check_for_replies():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SENDER_EMAIL, SENDER_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, 'ALL')
        if not messages[0]:
            return
            
        msg_ids = messages[0].split()
        last_5_ids = msg_ids[-5:] 
        
        all_emails = [x.lower().strip() for x in sheet.col_values(2)] 

        for num in last_5_ids:
            res, msg_data_raw = mail.fetch(num, "(RFC822)")
            for response in msg_data_raw:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    sender = email.utils.parseaddr(msg['from'])[1].lower().strip()
                    
                    if sender in all_emails:
                        actual_row = all_emails.index(sender) + 1
                        current_status = sheet.cell(actual_row, 4).value
                        
                        if current_status == "Not Replied":
                            reply_content = get_email_body(msg)
                            
                            # Sheet se Name aur Phone fetch karna taake AI function ko pass kar sakein
                            user_name = sheet.cell(actual_row, 1).value
                            user_phone = str(sheet.cell(actual_row, 3).value)
                            
                            ai_decision = analyze_sentiment(reply_content, user_name, user_phone)
                            sheet.update_cell(actual_row, 4, ai_decision)
                            print(f"🤖 AI classified {sender} as: {ai_decision}")
        
        mail.close()
        mail.logout()
    except Exception as e:
        print(f"❌ Check Replies Error: {e}")


# ==========================================
# 3. BACKGROUND SCHEDULER
# Maqsad: check_for_replies function ko background mein khud ba khud chalate rehna.
# ==========================================
scheduler = BackgroundScheduler()
scheduler.add_job(check_for_replies, 'interval', minutes=1)
scheduler.start()


# ==========================================
# 4. API ENDPOINTS (Frontend Next.js ke liye)
# ==========================================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class UserData(BaseModel):
    name: str
    email: EmailStr
    phone: str

# Maqsad: Jab Next.js se naya lead aaye, to usay Sheet mein save karna, 
# Welcome Email bhejna aur Phase 6 ka Welcome WhatsApp bhejna.
@app.post("/register")
async def register_user(user: UserData):
    try:
        emails = [e.lower().strip() for e in sheet.col_values(2)]
        phones = sheet.col_values(3)

        if user.email.lower().strip() in emails:
            raise HTTPException(status_code=400, detail="Email already registered!")
        
        if str(user.phone) in phones:
            raise HTTPException(status_code=400, detail="Phone number already registered!")

        # Data sheet mein daalna
        new_row = [user.name, user.email, user.phone, "Not Replied"]
        sheet.append_row(new_row)
        
        # 1. Welcome Email Bhejna
        send_welcome_email(user.email, user.name)
        
        # 2. Welcome WhatsApp Bhejna
        whatsapp_body = f"Assalam-o-Alaikum {user.name}! Humne aapka inquiry receive kar li hai. Hamari team jald aap se rabta karegi."
        send_whatsapp_msg(user.phone, whatsapp_body)

        return {"message": "Success"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"❌ Register Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Maqsad: Dashboard ko stats dena (Kitne total leads hain, kitne reply aaye, etc.)
@app.get("/stats")
async def get_stats():
    try:
        all_records = sheet.get_all_records()
        replied_leads = ["Hot Lead", "Cold Lead", "Follow-up", "Replied"]
        return {
            "total": len(all_records),
            "replied": sum(1 for r in all_records if r.get("Status") in replied_leads),
            "pending": sum(1 for r in all_records if r.get("Status") == "Not Replied"),
            "data": all_records 
        }
    except Exception as e:
        print(f"❌ Stats Error: {e}")
        raise HTTPException(status_code=500, detail="Stats failed")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)