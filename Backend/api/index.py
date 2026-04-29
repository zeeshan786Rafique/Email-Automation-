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


# 🛠️ Path Fix: .env file Backend root mein hai, to ye wahan se load karega
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# 🛠️ FIX: Old oauth2client ki jagah modern Google Auth use kiya hai
from google.oauth2.service_account import Credentials 

import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Scheduler ko Vercel par nikal dena behtar hai (Cron Jobs use karein)
from api.whatsapp_handler import send_whatsapp_msg

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "shaniizr786rafique@gmail.com"
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)


# 🛠️ Import Fix: Dono files same folder mein hain
try:
    from api.whatsapp_handler import send_whatsapp_msg
except ImportError:
    from whatsapp_handler import send_whatsapp_msg

# ==========================================
# GLOBAL VARIABLE SETUP
# ==========================================
sheet = None

# ==========================================
# GOOGLE SHEETS SETUP (Vercel Friendly)
# ==========================================
def get_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # 1. Vercel Check
        creds_json = os.getenv("credentials_json")
        
        if creds_json:
            creds_dict = json.loads(creds_json)
            if isinstance(creds_dict, str): creds_dict = json.loads(creds_dict)
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            # 2. Local File Check (Image ke mutabiq credentials.json parent folder mein hai)
            # __file__ is index.py, .parent is api/, .parent.parent is Backend/
            local_creds_path = Path(__file__).resolve().parent.parent / "credentials.json"
            
            if local_creds_path.exists():
                print(f"🏠 Found local credentials at: {local_creds_path}")
                creds = Credentials.from_service_account_file(str(local_creds_path), scopes=scope)
            else:
                print(f"❌ Error: credentials.json not found at {local_creds_path}")
                return None
                
        gs_client = gspread.authorize(creds)
        return gs_client.open("Email Automation with python").sheet1
    except Exception as e:
        print(f"❌ Connection Detail Error: {str(e)}")
        return None

# Initial connection attempt
sheet = get_gsheet()

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def format_pakistani_phone(phone: str) -> str:
    """Cleans and formats phone numbers to standard format for WhatsApp."""
    if not phone:
        return ""
    
    # Remove all non-numeric characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if cleaned.startswith("+92"):
        return cleaned
    elif cleaned.startswith("92") and len(cleaned) == 12:
        return "+" + cleaned
    elif cleaned.startswith("03") and len(cleaned) == 11:
        return "+92" + cleaned[1:]
    elif cleaned.startswith("3") and len(cleaned) == 10:
        return "+92" + cleaned
    
    return cleaned

def analyze_sentiment(reply_text, user_name, user_phone):
    if not reply_text.strip():
        return "Replied"
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
        
        if "Hot Lead" in category:
            formatted_phone = format_pakistani_phone(user_phone)
            # Admin Notification
            send_whatsapp_msg("+923091053298", f"📢 *New Hot Lead!*\nUser: {user_name}\nReply: {reply_text}")
            # User Notification
            if formatted_phone:
                send_whatsapp_msg(formatted_phone, "Thank you for your interest! We will contact you soon.")
        return category
    except Exception as e:
        print(f"❌ Groq API Error: {e}")
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

def send_welcome_email(to_email, user_name):
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
    except Exception as e: print(f"❌ SMTP Error: {e}")

# ==========================================
# API ENDPOINTS
# ==========================================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class UserData(BaseModel):
    name: str
    email: EmailStr
    phone: str

@app.get("/")
def read_root():
    global sheet
    # Vercel cold-start recovery
    if sheet is None:
        sheet = get_gsheet()
    return {"status": "Backend is Running", "sheets_connected": sheet is not None}

@app.post("/register")
async def register_user(user: UserData):
    global sheet 
    if sheet is None:
        try:
            sheet = get_gsheet()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Google Sheet Connection Failed: {str(e)}")

    if sheet is None:
        raise HTTPException(status_code=500, detail="Error: Google Sheet is not connected. Check Vercel logs.")

    # Duplicate check and formatting
    formatted_phone = format_pakistani_phone(user.phone)
    existing_emails = sheet.col_values(2)
    
    if user.email in existing_emails:
        return {"status": "User already exists", "email": user.email}
        
    try:
        # Append data to sheet (Name, Email, Phone, Status)
        sheet.append_row([user.name, user.email, formatted_phone, "Not Replied"])
        send_welcome_email(user.email, user.name)
        return {"status": "Success", "message": "User registered successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to insert record: {str(e)}")

@app.get("/check-replies")
async def manual_check():
    global sheet
    if sheet is None: sheet = get_gsheet()
    
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SENDER_EMAIL, SENDER_PASSWORD)
        mail.select("inbox")
        
        # 1. Sirf un emails ko target karein jo hamari sheet mein "Not Replied" hain
        all_records = sheet.get_all_records()
        processed_count = 0

        for idx, row in enumerate(all_records):
            # Row index sheet mein (idx + 2) hota hai kyunke 1st row header hai
            row_num = idx + 2
            current_status = str(row.get("Status", "")).strip()
            user_email = row.get("Email", "").lower().strip()

            if current_status == "Not Replied":
                # Gmail mein is specific email ke replies dhoondhein
                status, messages = mail.search(None, f'FROM "{user_email}"')
                
                if messages[0]:
                    # Mil gaya! Sab se latest reply uthayein
                    latest_msg_num = messages[0].split()[-1]
                    res, msg_data = mail.fetch(latest_msg_num, "(RFC822)")
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    body = get_email_body(msg)
                    name = row.get("Name")
                    phone = row.get("Phone")
                    
                    # AI Analysis (Hot Lead, Cold Lead, Follow-up)
                    decision = analyze_sentiment(body, name, phone)
                    
                    # Sheet Update
                    sheet.update_cell(row_num, 4, decision)
                    processed_count += 1

        mail.logout()
        return {"status": "success", "processed": processed_count, "message": f"{processed_count} replies found and updated."}
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/stats")
async def get_stats():
    global sheet
    if sheet is None: sheet = get_gsheet()
    if sheet is None: return {"error": "Sheet not connected"}
    
    try:
        all_records = sheet.get_all_records()
        
        # Original 3 Categories logic
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