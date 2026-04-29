from groq import Groq
import os
import json
import re
import sys
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

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Import WhatsApp handler
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
                print(f"[LOG] 🏠 Local credentials found at: {local_creds_path}", flush=True)
                creds = Credentials.from_service_account_file(str(local_creds_path), scopes=scope)
            else:
                print(f"[ERROR] ❌ credentials.json not found!", flush=True)
                return None
                
        gs_client = gspread.authorize(creds)
        print("[LOG] ✅ Google Sheets Connected Successfully.", flush=True)
        return gs_client.open("Email Automation with python").sheet1
    except Exception as e:
        print(f"[ERROR] ❌ Sheet Connection Error: {str(e)}", flush=True)
        return None

sheet = get_gsheet()

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def format_pakistani_phone(phone: str) -> str:
    if not phone: return ""
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    if cleaned.startswith("+92"): return cleaned
    elif cleaned.startswith("92") and len(cleaned) == 12: return "+" + cleaned
    elif cleaned.startswith("03") and len(cleaned) == 11: return "+92" + cleaned[1:]
    elif cleaned.startswith("3") and len(cleaned) == 10: return "+92" + cleaned
    return cleaned

# Strict Digits Extractor for Duplicate Validation
def extract_digits(phone: str) -> str:
    return re.sub(r'\D', '', str(phone))

def analyze_sentiment(reply_text, user_name, user_phone):
    if not reply_text.strip(): return "Replied"
    
    print(f"[LOG] 🧠 AI Classifying reply from: {user_name}...", flush=True)
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
        print(f"[LOG] 🤖 AI Decision: {category}", flush=True)
        
        if "Hot Lead" in category:
            formatted_phone = format_pakistani_phone(user_phone)
            print(f"[LOG] 🔥 Hot Lead Action: Sending WhatsApp notification!", flush=True)
            send_whatsapp_msg("+923091053298", f"📢 *New Hot Lead!*\nUser: {user_name}\nReply: {reply_text}")
            if formatted_phone:
                send_whatsapp_msg(formatted_phone, "Thank you for your interest! We will contact you soon.")
        return category
    except Exception as e:
        print(f"[ERROR] ❌ AI Error: {e}", flush=True)
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
            
        # Clean email trailing quotes
        cleaned_body = body.split("On Sun, Apr")[0].split("-----Original Message-----")[0].split(">")[0].strip()
        return cleaned_body
    except Exception as e: 
        print(f"[ERROR] Parsing body: {e}", flush=True)
        return ""

class User(BaseModel):
    name: str
    email: str
    phone: str

def send_email(to_email, user_name):
    print(f"[LOG] 📧 Sending Welcome Email to: {to_email}...", flush=True)
    try:
        message = MIMEMultipart()
        message["From"] = SENDER_EMAIL
        message["To"] = to_email
        message["Subject"] = "Welcome to Our Platform! 🚀"
        body = f"Hi {user_name},\n\nAapka registration successful ho gaya hai."
        message.attach(MIMEText(body, "plain"))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(message)
        server.quit()
        print(f"[LOG] ✅ Welcome Email Sent to {to_email}!", flush=True)
    except Exception as e: 
        print(f"[ERROR] ❌ SMTP Email Error: {e}", flush=True)

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
    
    print(f"\n--- 📥 NEW REGISTRATION ---", flush=True)
    
    try:
        all_data = sheet.get_all_records()
        
        # 1. Incoming Data ko clean karein
        incoming_email = user.email.lower().strip()
        # Phone se har kism ka character (+, -, space, zero) ura kar sirf aakhri 10 digits lein
        incoming_phone_digits = extract_digits(user.phone)[-10:] 
        
        print(f"[LOG] Validating: Email={incoming_email}, Clean Phone={incoming_phone_digits}", flush=True)

        # 2. Sheet ka data check karein
        for row in all_data:
            # Email Check
            if str(row.get("Email", "")).lower().strip() == incoming_email:
                print(f"[LOG] 🚫 Duplicate Email Found", flush=True)
                return {"status": "error", "message": "Email already registered."}
            
            # Phone Check (Sheet ke number ko bhi clean karke sirf aakhri 10 digits match karein)
            sheet_phone = extract_digits(str(row.get("Phone", "")))[-10:]
            if sheet_phone == incoming_phone_digits:
                print(f"[LOG] 🚫 Duplicate Phone Found: {sheet_phone}", flush=True)
                return {"status": "error", "message": "Phone number already exists."}

        # Agar koi duplicate nahi mila to save karein
        new_row = [user.name, user.email, user.phone, "Not Replied"]
        sheet.append_row(new_row)
        print(f"[LOG] ✅ Data Saved Successfully.", flush=True)

        send_email(user.email, user.name)
        return {"status": "success", "message": "Registration Successful!"}

    except Exception as e:
        print(f"[ERROR] ❌ Crash: {str(e)}", flush=True)
        return {"status": "error", "message": str(e)}


@app.get("/check-replies")
async def manual_check():
    global sheet
    if sheet is None: sheet = get_gsheet()
    
    print(f"\n--- 🔍 STARTING INBOX CHECK ---", flush=True)
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SENDER_EMAIL, SENDER_PASSWORD)
        mail.select("inbox")
        print("[LOG] ✅ Gmail Inbox Connected.", flush=True)
        
        all_records = sheet.get_all_records()
        found_any = 0

        for idx, row in enumerate(all_records):
            row_num = idx + 2
            email_addr = row.get("Email", "").lower().strip()
            status_now = str(row.get("Status", "")).strip()

            if status_now == "Not Replied":
                print(f"[LOG] 🔎 Searching inbox for replies from: {email_addr}", flush=True)
                res, messages = mail.search(None, f'(FROM "{email_addr}" UNSEEN)')                
                # If email bytes exist
                if messages[0]:
                    latest_id = messages[0].split()[-1]
                    _, data = mail.fetch(latest_id, "(RFC822)")
                    msg = email.message_from_bytes(data[0][1])
                    reply_text = get_email_body(msg)

                    print(f"[LOG] 📬 Raw Reply Extracted: {reply_text[:50]}...", flush=True)

                    if reply_text:
                        decision = analyze_sentiment(reply_text, row.get("Name"), row.get("Phone"))
                        
                        # UPDATE STATUS IN COLUMN 4 (D)
                        sheet.update_cell(row_num, 4, decision)
                        print(f"[LOG] ✍️ Sheet Updated! Row {row_num}, Status -> {decision}", flush=True)
                        found_any += 1
                    else:
                        print(f"[LOG] ⚠️ Email found but body was empty for {email_addr}", flush=True)
                else:
                    print(f"[LOG] 📭 No reply found yet from {email_addr}.", flush=True)

        mail.logout()
        print(f"[LOG] ✅ Check Complete. Total Statuses Updated: {found_any}", flush=True)
        print(f"--- END OF INBOX CHECK ---\n", flush=True)
        return {"status": "success", "message": f"Updated {found_any} users."}
    except Exception as e:
        print(f"[ERROR] ❌ Inbox Check Failed: {str(e)}", flush=True)
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