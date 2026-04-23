from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = FastAPI()

# Frontend (Next.js) ko allow karne ke liye CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Live project mein yahan specific URL aayega
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Sheets Configuration
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    # Sheet ka naam wahi hona chahiye jo aapne rakha hai
    sheet = client.open("Email Automation with python").sheet1
    print("✅ Google Sheets connected successfully!")
except Exception as e:
    print(f"❌ Connection Error: {e}")

# Data Validation Model
class UserData(BaseModel):
    name: str
    email: EmailStr
    phone: str

@app.post("/register")
async def register_user(user: UserData):
    try:
        # 1. Seedha columns ka data uthayein (Headers ka lafra hi khatam)
        # Column 2 = Email, Column 3 = Phone
        emails = sheet.col_values(2)
        phones = sheet.col_values(3)

        # 2. Duplicate Check
        if user.email in emails:
            raise HTTPException(status_code=400, detail="This email is already registered!")
        
        if user.phone in phones:
            raise HTTPException(status_code=400, detail="This phone number is already registered!")

        # 3. Agar duplicate nahi hai to save karein
        # Order: Name (Col 1), Email (Col 2), Phone (Col 3), Status (Col 4)
        new_row = [user.name, user.email, user.phone, "Not Replied"]
        sheet.append_row(new_row)

        return {"message": "Registration successful!"}

    except HTTPException as http_exc:
        # Ye frontend ko 400 error bhejega (Email/Phone exists)
        raise http_exc
    except Exception as e:
        # Ye terminal mein error dikhayega agar koi aur masla hua
        print(f"❌ Backend Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)