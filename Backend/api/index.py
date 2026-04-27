from groq import Groq
import os
import json
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
# Scheduler ko Vercel par nikal dena behtar hai (Cron Jobs use karein)
from whatsapp_handler import send_whatsapp_msg

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "shaniizr786rafique@gmail.com"
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# GOOGLE SHEETS SETUP (Vercel Friendly)
# ==========================================
def get_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # 1. Pehle Environment Variable check karein (Sabse behtareen tareeqa)
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # 2. Agar local pe hain to file dhoondein
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            
        gs_client = gspread.authorize(creds)
        return gs_client.open("Email Automation with python").sheet1
    except Exception as e:
        print(f"❌ Sheets Connection Error: {e}")
        return None

# Global sheet variable
sheet = get_gsheet()

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

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
            send_whatsapp_msg("+923091053298", f"📢 *New Hot Lead!*\nUser: {user_name}\nReply: {reply_text}")
            if user_phone:
                send_whatsapp_msg(user_phone, "Thank you for your interest! We will contact you soon.")
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
    return {"status": "Backend is Running", "sheets_connected": sheet is not None}

@app.post("/register")
async def register_user(user: UserData):
    global sheet
    
    # 1. Check if Google Sheet is connected
    if sheet is None:
        sheet = get_gsheet() # Dobara koshish karein
        if sheet is None:
            raise HTTPException(status_code=500, detail="Error: Google Sheet is not connected. Check your credentials_json.")

    try:
        # 2. Check for duplicate Email/Phone
        try:
            emails = [e.lower().strip() for e in sheet.col_values(2)]
            phones = sheet.col_values(3)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading from Google Sheet: {str(e)}")

        if user.email.lower().strip() in emails:
            raise HTTPException(status_code=400, detail="Email already registered!")
        
        if str(user.phone) in phones:
            raise HTTPException(status_code=400, detail="Phone number already registered!")

        # 3. Append Data
        try:
            new_row = [user.name, user.email, user.phone, "Not Replied"]
            sheet.append_row(new_row)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error adding row to Sheet: {str(e)}")
        
        # 4. Try sending Welcome Email
        try:
            send_welcome_email(user.email, user.name)
        except Exception as e:
            print(f"SMTP Warning: {e}") # Ispe crash nahi karenge, sirf log karenge

        # 5. Try sending WhatsApp
        try:
            whatsapp_body = f"Assalam-o-Alaikum {user.name}! Humne aapka inquiry receive kar li hai."
            send_whatsapp_msg(user.phone, whatsapp_body)
        except Exception as e:
            print(f"WhatsApp Warning: {e}")

        return {"message": "Success", "status": "User registered and sheet updated"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Full Register Error: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected System Error: {str(e)}")
        
    global sheet
    if not sheet: sheet = get_gsheet() # Re-connect if lost
    
    try:
        emails = [e.lower().strip() for e in sheet.col_values(2)]
        if user.email.lower().strip() in emails:
            raise HTTPException(status_code=400, detail="Email already registered!")

        sheet.append_row([user.name, user.email, user.phone, "Not Replied"])
        send_welcome_email(user.email, user.name)
        send_whatsapp_msg(user.phone, f"Assalam-o-Alaikum {user.name}! Inquiry received.")
        return {"message": "Success"}
    except Exception as e:
        print(f"❌ Register Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Yeh endpoint ab manual ya Vercel Cron se hit hoga
@app.get("/check-replies")
async def manual_check():
    global sheet
    if not sheet: sheet = get_gsheet()
    
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SENDER_EMAIL, SENDER_PASSWORD)
        mail.select("inbox")
        status, messages = mail.search(None, 'UNSEEN') # Sirf unread check karein efficiency ke liye
        
        if not messages[0]:
            return {"message": "No new replies"}

        all_emails = [x.lower().strip() for x in sheet.col_values(2)]
        for num in messages[0].split():
            res, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            sender = email.utils.parseaddr(msg['from'])[1].lower().strip()

            if sender in all_emails:
                row_idx = all_emails.index(sender) + 1
                if sheet.cell(row_idx, 4).value == "Not Replied":
                    body = get_email_body(msg)
                    name = sheet.cell(row_idx, 1).value
                    phone = sheet.cell(row_idx, 3).value
                    decision = analyze_sentiment(body, name, phone)
                    sheet.update_cell(row_idx, 4, decision)
        
        mail.logout()
        return {"status": "Done"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/stats")
async def get_stats():
    global sheet
    if not sheet: sheet = get_gsheet()
    all_records = sheet.get_all_records()
    return {"total": len(all_records), "data": all_records}