import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from database import supabase

app = FastAPI(title="Gold Branch Management API", version="1.0.0")

# மொபைல் / பிரவுசர் கோரிக்கைகளுக்கான CORS அனுமதி
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static கோப்புறையை இணைத்தல் (Frontend UI)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# உள்ளீட்டுத் தரவு சரிபார்ப்பு (Pydantic Schema)
class PacketRecord(BaseModel):
    packet_id: str = Field(..., description="பாக்கெட் அல்லது ரசீது எண்")
    customer_name: str = Field(..., description="வாடிக்கையாளர் பெயர்")
    phone: str = Field(..., description="மொபைல் எண்")
    weight_grams: float = Field(..., gt=0, description="தங்கத்தின் எடை (கிராமில்)")
    advance_amount: float = Field(0.0, ge=0, description="முன்பணம் அல்லது கடன் தொகை")
    branch_name: str = Field(..., description="கிளையின் பெயர்")

# ரூட் பாதை - மொபைல் திரையைக் காண்பித்தல்
@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI சர்வர் இயங்குகிறது. static/index.html கோப்பு இணைக்கப்படவில்லை."}

# ஹெல்த் செக் எண்ட்பாயிண்ட் (Health Check)
@app.get("/health")
def health_check():
    return {"status": "active", "service": "Gold FastAPI Backend"}

# வாடிக்கையாளர் & பாக்கெட் பதிவு செய்யும் API
@app.post("/api/packet/add")
def add_packet(data: PacketRecord):
    try:
        # test_packets அட்டவணையின் காலம்களுக்கு ஏற்றவாறு அமைத்தல்
        record = {
            "packet_id": data.packet_id,
            "customer_name": data.customer_name,
            "phone": data.phone,
            "weight": data.weight_grams,
            "advance": data.advance_amount,
            "branch": data.branch_name
        }
        
        # முக்கிய மாற்றம்: இங்கே "test_packets" என்று சரியாக இருக்க வேண்டும்
        response = supabase.table("test_packets").insert(record).execute()
        
        return {
            "status": "success",
            "message": "விவரங்கள் வெற்றிகரமாகச் சேமிக்கப்பட்டன",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"டேட்டாபேஸ் பிழை: {str(e)}")
