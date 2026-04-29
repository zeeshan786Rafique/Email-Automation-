from groq import Groq
import os
import json
import re
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import gspread
from pathlib import Path
from google.oauth2.service_account import Credentials 

import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Path Fix: .env file Backend root mein hai, to ye wahan se load karega
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Import Fix: Dono files same folder mein hain
try:
    from api.whatsapp_handler import send_whatsapp_msg
except ImportError:
    from whatsapp_handler import send_whatsapp_msg

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "shaniizr786rafique@gmail.com"
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# GLOBAL VARIABLE SETUP
# ==========================================
sheet = None

# ==========================================
# GOOGLE SHEETS SETUP
# ==========================================
def get_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_json = os.getenv("credentials_json")
        
        if creds_json:
            creds_dict = json.loads(creds_json)
            if isinstance(creds_dict, str): creds_dict = json.loads(creds_dict)
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            local_creds_path = Path(__file__).resolve().parent.parent / "credentials.json"
            if local_creds_path.exists():
                print(f"[LOG] 🏠 Found local credentials at: {local_creds_path}")
                creds = Credentials.from_service_account_file(str(local_creds_path), scopes=scope)
            else:
                print(f"[ERROR] ❌ credentials.json not found at {local_creds_path}")
                return None
                
        gs_client = gspread.authorize(creds)
        print("[LOG] ✅ Google Sheets Connected Successfully.")
        return gs_client.open("Email Automation with python").sheet1
    except Exception as e:
        print(f"[ERROR] ❌ Connection Detail Error: {str(e)}")
        return None

# Initial connection attempt
sheet = get_gsheet()

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def format_pakistani_phone(phone: str) -> str:
    if not phone: return ""
    cleaned = re.sub(r'[^\d+]', '', phone)
    if cleaned.startswith("+92"): return cleaned
    elif cleaned.startswith("92") and len(cleaned) == 12: return "+" + cleaned
    elif cleaned.startswith("03") and len(cleaned) == 11: return "+92" + cleaned[1:]
    elif cleaned.startswith("3") and len(cleaned) == 10: return "+92" + cleaned
    return cleaned

def analyze_sentiment(reply_text, user_name, user_phone):
    if not reply_text.strip(): return "Replied"
    
    print(f"[LOG] 🧠 Sending reply of {user_name} to AI for Analysis...")
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a lead classifier. Only answer with exactly one of these: 'Hot Lead', 'Cold Lead', or 'Follow-up'."},
                {"role": "user", "content": f"Classify this email: {reply_text}"}
            ],
            model="llama-3.1-8b-instant", 
            temperature=0.1,
        )
        category = chat_completion.choices[0].message.content.strip().replace("*", "").replace("'", "").replace('"', '').replace(".", "")
        print(f"[LOG] 🤖 AI Decision Output: {category}")
        
        if "Hot Lead" in category:
            formatted_phone = format_pakistani_phone(user_phone)
            print(f"[LOG] 🔥 Hot Lead detected! Sending WhatsApp notifications...")
            send_whatsapp_msg("+923091053298", f"📢 *New Hot Lead!*\nUser: {user_name}\nReply: {reply_text}")
            if formatted_phone:
                send_whatsapp_msg(formatted_phone, "Thank you for your interest! We will contact you soon.")
        return category
    except Exception as e:
        print(f"[ERROR] ❌ Groq API Error: {e}")
        return "Replied"

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
        return body.split("On Sun, Apr")[0].split("-----Original Message-----")[0].strip()
    except: return ""

class User(BaseModel):
    name: str
    email: str
    phone: str

# FIX: Function ka naam theek kar diya taake /register me error na aye
def send_email(to_email, user_name):
    print(f"\n[LOG] 📧 Preparing to send Welcome Email to: {to_email}")
    try:
        message = MIMEMultipart()
        message["From"] = SENDER_EMAIL
        message["To"] = to_email
        message["Subject"] = "Welcome to Our Platform! 🚀"
        body = f"Hi {user_name},\n\nAapka registration successful ho gaya hai."
        message.attach(MIMEText(body, "plain"))
        
        print("[LOG] 🔄 Connecting to SMTP Server (smtp.gmail.com)...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(message)
        server.quit()
        print(f"[LOG] ✅ Welcome Email successfully sent to {to_email}!")
    except Exception as e: 
        print(f"[ERROR] ❌ SMTP Error while sending email: {e}")

# ==========================================
# API ENDPOINTS
# ==========================================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def read_root():
    global sheet
    if sheet is None: sheet = get_gsheet()
    return {"status": "Backend is Running", "sheets_connected": sheet is not None}

@app.post("/register")
async def register_user(user: User):
    global sheet
    if sheet is None: sheet = get_gsheet()
    print(f"\n==========================================")
    print(f"[LOG] 📥 NEW REGISTRATION REQUEST RECEIVED")
    print(f"[LOG] Name: {user.name} | Email: {user.email} | Phone: {user.phone}")
    
    try:
        all_data = sheet.get_all_records()
        existing_emails = [str(row.get("Email", "")).lower().strip() for row in all_data]
        existing_phones = [str(row.get("Phone", "")).strip() for row in all_data]

        print("[LOG] 🔍 Checking for duplicates in Google Sheets...")
        if user.email.lower().strip() in existing_emails:
            print(f"[LOG] 🚫 Registration Denied: Email {user.email} already exists.")
            return {"status": "error", "message": "Email already registered."}
        
        if str(user.phone).strip() in existing_phones:
            print(f"[LOG] 🚫 Registration Denied: Phone {user.phone} already exists.")
            return {"status": "error", "message": "Phone number already exists."}

        new_row = [user.name, user.email, user.phone, "Not Replied"]
        sheet.append_row(new_row)
        print(f"[LOG] ✅ Successfully saved {user.name} to Google Sheets.")

        # Email bhejna
        send_email(user.email, user.name)
        print(f"==========================================\n")
        return {"status": "success", "message": "Registration Successful!"}

    except Exception as e:
        print(f"[ERROR] ❌ Registration Process Failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/check-replies")
async def manual_check():
    global sheet
    if sheet is None: sheet = get_gsheet()
    
    print(f"\n==========================================")
    print("\n[LOG] 🔍 INITIATING GMAIL INBOX CHECK FOR REPLIES...")
    try:
        print("[LOG] 🔄 Connecting to IMAP Server (imap.gmail.com)...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SENDER_EMAIL, SENDER_PASSWORD)
        mail.select("inbox")
        print("[LOG] ✅ Successfully connected and opened Inbox.")
        
        all_records = sheet.get_all_records()
        found_any = 0

        for idx, row in enumerate(all_records):
            row_num = idx + 2
            email_addr = row.get("Email", "").lower().strip()
            status_now = row.get("Status", "").strip()

            if status_now == "Not Replied":
                print(f"\n[LOG] 🔎 Checking replies from: {email_addr}")
                res, messages = mail.search(None, f'FROM "{email_addr}"')
                
                if messages[0]:
                    print(f"[LOG] 📬 Email found from {email_addr}! Fetching details...")
                    latest_id = messages[0].split()[-1]
                    _, data = mail.fetch(latest_id, "(RFC822)")
                    msg = email.message_from_bytes(data[0][1])
                    reply_text = get_email_body(msg)

                    print(f"[LOG] 📝 Extracted Reply: '{reply_text[:100]}...'")

                    # AI Classifier
                    decision = analyze_sentiment(reply_text, row.get("Name"), row.get("Phone"))
                    
                    print(f"[LOG] ✍️ Updating Google Sheet Status to: {decision}")
                    sheet.update_cell(row_num, 4, decision)
                    found_any += 1
                else:
                    print(f"[LOG] 📭 No reply found yet from {email_addr}.")

        mail.logout()
        print(f"\n[LOG] ✅ Inbox check complete. Total statuses updated: {found_any}")
        print(f"==========================================\n")
        return {"status": "success", "message": f"Updated {found_any} users."}
    except Exception as e:
        print(f"[ERROR] ❌ Manual Check Failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/stats")
async def get_stats():
    global sheet
    if sheet is None: sheet = get_gsheet()
    if sheet is None: return {"error": "Sheet not connected"}
    
    try:
        all_records = sheet.get_all_records()
        
        hot_leads = [r for r in all_records if str(r.get("Status")).strip() == "Hot Lead"]
        pending = [r for r in all_records if str(r.get("Status")).strip() in ["Not Replied", "Follow-up"]]
        cold_leads = [r for r in all_records if str(r.get("Status")).strip() == "Cold Lead"]

        return {
            "total": len(all_records),
            "hot_leads": len(hot_leads),
            "pending_followups": len(pending),
            "cold_leads": len(cold_leads),
            "data": all_records
        }
    except Exception as e:
        return {"error": str(e)}