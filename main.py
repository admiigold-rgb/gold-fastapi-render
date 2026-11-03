import os
import random
import requests
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from database import supabase

app = FastAPI(
    title="Gold Branch Management - Safe Test Environment with Auth & OTP",
    version="1.4.0",
    description="Branch Management System with Staff Auth, Pawn Cart, Denominations and Fast2SMS DLT OTP"
)

# CORS அனுமதி
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static கோப்புறை இணைப்பு (Frontend UI)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Fast2SMS DLT SMS Function ---

def send_fast2sms_otp(mobile_no: str, otp_code: str, customer_name: str, amount: float, txn_type: str = "receive"):
    """
    txn_type: "receive" -> வாடிக்கையாளர் பணம் பெறும்போது (நாம் கொடுப்பது GL/FD/RD பட்டுவாடா) (DLT ID: 229683)
              "pay"     -> வாடிக்கையாளர் பணம் செலுத்தும்போது (நாம் வாங்குவது வட்டி/கட்டணம்) (DLT ID: 229682)
    """
    try:
        api_key = os.getenv("FAST2SMS_API_KEY", "eBGQYanRZNKVCpMSg3KB5kUxY2QhDnOjxesh3Hqr7FOG792XV9wut4TPhQia")
        clean_mobile = "".join(filter(str.isdigit, str(mobile_no)))[-10:]
        url = "https://www.fast2sms.com/dev/bulkV2"

        headers = {
            "authorization": api_key.strip(),
            "Content-Type": "application/x-www-form-urlencoded",
            "accept": "application/json",
        }

        formatted_amount = f"{abs(amount):,.2f}"
        var_values = f"{customer_name}|{formatted_amount}|{otp_code}"
        dlt_msg_id = "229683" if txn_type == "receive" else "229682"

        payload = {
            "route": "dlt",
            "sender_id": "MUTUSI",
            "message": dlt_msg_id,
            "variables_values": var_values,
            "numbers": clean_mobile,
            "flash": "0"
        }

        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        res_json = resp.json()

        if res_json.get("return") is True:
            return True, "SMS வெற்றிகரமாக அனுப்பப்பட்டது!"

        err_msg = res_json.get("message") or str(res_json)
        return False, str(err_msg)
    except Exception as e:
        return False, f"SMS இணைப்புப் பிழை: {str(e)}"


# --- Pydantic Data Models ---

class LoginRequest(BaseModel):
    username: str = Field(..., description="பயனர் பெயர்")
    password: str = Field(..., description="கடவுச்சொல்")

class NewCustomerKYC(BaseModel):
    name: str = Field(..., description="வாடிக்கையாளர் பெயர்")
    mobile: str = Field(..., description="முதன்மை மொபைல் எண்")
    mobile2: Optional[str] = Field(None, description="இரண்டாவது மொபைல் எண்")
    guardian_name: Optional[str] = Field(None, description="தந்தை / கணவர் பெயர்")
    address: Optional[str] = Field(None, description="முழு முகவரி")
    branch_id: int = Field(default=1, description="கிளை அடையாள எண்")

class CustomerVisitEntry(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் ஐடி")
    branch_id: int = Field(default=1, description="கிளை ஐடி")
    purpose: Optional[str] = Field(default="REGULAR_TRANSACTION", description="வருகையின் நோக்கம்")

class CustomerUpdateRequest(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் ஐடி")
    branch_id: int = Field(default=1, description="கிளை ஐடி")
    requested_changes: Dict[str, Any] = Field(..., description="மாற்றப்பட வேண்டிய விபரங்கள்")

class OrnamentItem(BaseModel):
    item_type: str = Field(..., description="நகை வகை (செயின், வளையல்)")
    item_count: int = Field(..., description="எண்ணிக்கை")
    gross_weight: float = Field(..., description="மொத்த எடை")
    net_weight: float = Field(..., description="நிகர எடை")
    purity: str = Field(..., description="தரம் (916 KDM, 22CT)")

class NewGoldLoanEntry(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் ஐடி")
    branch_id: int = Field(default=1, description="கிளை ஐடி")
    loan_no: str = Field(..., description="நகைக்கடன் எண்")
    scheme_name: str = Field(..., description="திட்டத்தின் பெயர்")
    loan_amount: float = Field(..., description="கடன் தொகை (நாம் கொடுப்பது)")
    charges_amount: float = Field(default=0.0, description="கட்டணங்கள் (நாம் வாங்குவது)")
    photo_url: Optional[str] = None
    items: List[OrnamentItem] = Field(..., description="நகைகளின் பட்டியல்")

class DenominationCounts(BaseModel):
    c_500: int = 0
    c_200: int = 0
    c_100: int = 0
    c_50: int = 0
    c_20: int = 0
    c_10: int = 0
    c_coins: int = 0

class SendOtpPayload(BaseModel):
    customer_id: int
    mobile: str
    customer_name: str
    net_amount: float
    direction: str  # COMPANY_PAYABLE / CUSTOMER_PAYABLE

class SettleWithOtpPayload(BaseModel):
    customer_id: int
    branch_id: int = 1
    otp_code: str
    net_amount: float
    direction: str
    settlement_type: str
    cash_amount: float = 0.0
    bank_amount: float = 0.0
    bank_ref_no: Optional[str] = None
    bank_name: Optional[str] = None
    denominations: Optional[DenominationCounts] = None

class DirectSettlementPayload(BaseModel):
    customer_id: int
    branch_id: int = 1
    net_amount: float
    direction: str
    settlement_type: str
    cash_amount: float = 0.0
    bank_amount: float = 0.0
    bank_ref_no: Optional[str] = None
    bank_name: Optional[str] = None
    denominations: Optional[DenominationCounts] = None


# --- Endpoints ---

@app.get("/")
def serve_ui():
    """முகப்புத் திரை"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI சர்வர் இயங்குகிறது. static/index.html கோப்பு இணைக்கப்படவில்லை."}

@app.get("/health")
def health_check():
    """UptimeRobot கண்காணிப்புக்கான ஹெல்த் செக்"""
    return {"status": "active", "service": "Gold Branch API"}

# 1. பணியாளர் உள்நுழைவு (Staff Login) API
@app.post("/api/auth/login")
def staff_login(data: LoginRequest):
    try:
        clean_user = data.username.strip()
        clean_pass = data.password.strip()

        res = (
            supabase.table("test_users")
            .select("id, username, full_name, role, branch_id, branch_name, is_active")
            .eq("username", clean_user)
            .eq("password", clean_pass)
            .execute()
        )

        if not res.data:
            raise HTTPException(status_code=401, detail="பயனர் பெயர் அல்லது கடவுச்சொல் தவறானது!")

        user = res.data[0]
        if not user.get("is_active"):
            raise HTTPException(status_code=403, detail="இந்தக் கணக்கு முடக்கப்பட்டுள்ளது. தலைமை நிர்வாகியை அணுகவும்.")

        return {
            "status": "success",
            "message": "உள்நுழைவு வெற்றிகரமாக முடிந்தது!",
            "user": user
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"லாகின் பிழை: {str(e)}")

# 2. வாடிக்கையாளர் தேடல் (test_customers)
@app.get("/api/customer/search")
def search_customer(query: str = Query(..., min_length=1)):
    try:
        clean_query = query.strip()
        if clean_query.isdigit():
            res = (
                supabase.table("test_customers")
                .select("id, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active")
                .ilike("mobile", f"%{clean_query}%")
                .limit(10)
                .execute()
            )
        else:
            res = (
                supabase.table("test_customers")
                .select("id, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active")
                .ilike("name", f"%{clean_query}%")
                .limit(10)
                .execute()
            )
        return {"status": "success", "count": len(res.data), "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")

# 3. வருகைப் பதிவு (test_customer_visits)
@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    try:
        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "purpose": data.purpose
        }
        res = supabase.table("test_customer_visits").insert(record).execute()
        return {"status": "success", "message": "வருகை வெற்றிகரமாகப் பதிவானது", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வருகைப் பதிவு பிழை: {str(e)}")

# 4. புதிய வாடிக்கையாளர் KYC பதிவு (test_customers)
@app.post("/api/customer/new-kyc")
def create_kyc(data: NewCustomerKYC):
    try:
        clean_mobile = data.mobile.strip()
        existing = (
            supabase.table("test_customers")
            .select("id, name")
            .eq("mobile", clean_mobile)
            .execute()
        )
        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"இந்த மொபைல் எண் ஏற்கனவே சோதனைப் பதிவில் உள்ளது ({existing.data[0]['name']})."
            )

        record = {
            "name": data.name.strip(),
            "mobile": clean_mobile,
            "mobile2": data.mobile2.strip() if data.mobile2 else None,
            "guardian_name": data.guardian_name.strip() if data.guardian_name else None,
            "address": data.address.strip() if data.address else None,
            "branch_id": data.branch_id,
            "kyc_status": "PENDING",
            "is_active": True
        }
        res = supabase.table("test_customers").insert(record).execute()
        return {"status": "success", "message": "சோதனை KYC வெற்றிகரமாகச் சேமிக்கப்பட்டது.", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KYC பதிவு பிழை: {str(e)}")

# 5. விபர மாற்றக் கோரிக்கை (test_customer_update_requests)
@app.post("/api/customer/request-update")
def request_customer_update(data: CustomerUpdateRequest):
    try:
        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "requested_changes": data.requested_changes,
            "status": "PENDING"
        }
        res = supabase.table("test_customer_update_requests").insert(record).execute()
        return {"status": "success", "message": "சோதனை மாற்றக் கோரிக்கை சேமிக்கப்பட்டது.", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"மாற்றக் கோரிக்கை பிழை: {str(e)}")

# 6. புதிய நகைக்கடன் அடகு பதிவு (test_gold_loans & test_gold_loan_items)
@app.post("/api/loan/new-pawn")
def create_new_pawn(data: NewGoldLoanEntry):
    try:
        if not data.items:
            raise HTTPException(status_code=400, detail="குறைந்தது ஒரு நகையாவது பட்டியலில் சேர்க்கப்பட வேண்டும்.")

        total_gross = sum(i.gross_weight for i in data.items)
        total_net = sum(i.net_weight for i in data.items)
        net_payable = data.loan_amount - data.charges_amount

        loan_record = {
            "loan_no": data.loan_no.strip(),
            "customer_id": data.customer_id,
            "scheme_name": data.scheme_name,
            "total_gross_weight": round(total_gross, 3),
            "total_net_weight": round(total_net, 3),
            "loan_amount": data.loan_amount,
            "charges_amount": data.charges_amount,
            "net_payable_amount": net_payable,
            "photo_url": data.photo_url,
            "branch_id": data.branch_id,
            "status": "ACTIVE"
        }
        res_loan = supabase.table("test_gold_loans").insert(loan_record).execute()
        new_loan_id = res_loan.data[0]["id"]

        items_payload = []
        for i in data.items:
            items_payload.append({
                "loan_id": new_loan_id,
                "item_type": i.item_type.strip(),
                "item_count": i.item_count,
                "gross_weight": i.gross_weight,
                "net_weight": i.net_weight,
                "purity": i.purity
            })
        supabase.table("test_gold_loan_items").insert(items_payload).execute()

        return {
            "status": "success",
            "message": "நகைக்கடன் புதிய அடகு வெற்றிகரமாகச் சேமிக்கப்பட்டது.",
            "loan_id": new_loan_id,
            "net_payable": net_payable
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"அடகுப் பதிவு பிழை: {str(e)}")

# 7. SMS OTP உருவாக்கம் & அனுப்புதல்
@app.post("/api/otp/send")
def trigger_otp_sms(payload: SendOtpPayload):
    try:
        otp_code = str(random.randint(100000, 999999))
        txn_type = "receive" if payload.direction == "COMPANY_PAYABLE" else "pay"

        success, msg = send_fast2sms_otp(
            mobile_no=payload.mobile,
            otp_code=otp_code,
            customer_name=payload.customer_name,
            amount=payload.net_amount,
            txn_type=txn_type
        )

        if not success:
            raise HTTPException(status_code=502, detail=f"SMS அனுப்புவதில் தோல்வி: {msg}")

        supabase.table("test_transaction_otps").insert({
            "customer_id": payload.customer_id,
            "mobile": payload.mobile,
            "otp_code": otp_code,
            "net_amount": payload.net_amount,
            "txn_type": txn_type,
            "is_verified": False
        }).execute()

        return {"status": "success", "message": "OTP வாடிக்கையாளர் மொபைலுக்கு SMS மூலம் அனுப்பப்பட்டது."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OTP பிழை: {str(e)}")

# 8. OTP சரிபார்த்து செட்டில்மென்ட்டை முடித்தல் API
@app.post("/api/transaction/settle-with-otp")
def settle_with_otp(data: SettleWithOtpPayload):
    try:
        # A. OTP சரிபார்ப்பு
        otp_query = (
            supabase.table("test_transaction_otps")
            .select("id, otp_code, is_verified")
            .eq("customer_id", data.customer_id)
            .eq("is_verified", False)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not otp_query.data:
            raise HTTPException(status_code=400, detail="செல்லுபடியாகும் OTP கோரிக்கை எதுவும் இல்லை.")

        latest_otp = otp_query.data[0]
        if latest_otp["otp_code"] != data.otp_code.strip():
            raise HTTPException(status_code=400, detail="உள்ளிட்ட OTP தவறானது. மீண்டும் முயற்சிக்கவும்.")

        # B. ரொக்கத் தாள்கள் சரிபார்ப்பு
        if data.cash_amount > 0 and data.denominations:
            calc_cash = (
                data.denominations.c_500 * 500 +
                data.denominations.c_200 * 200 +
                data.denominations.c_100 * 100 +
                data.denominations.c_50 * 50 +
                data.denominations.c_20 * 20 +
                data.denominations.c_10 * 10 +
                data.denominations.c_coins
            )
            if round(calc_cash, 2) != round(data.cash_amount, 2):
                raise HTTPException(
                    status_code=400,
                    detail=f"தாள்களின் கூட்டுத்தொகை (₹{calc_cash}) ரொக்கத் தொகையுடன் (₹{data.cash_amount}) பொருந்தவில்லை."
                )

        # C. செட்டில்மென்ட் அட்டவணையில் சேமித்தல்
        settle_record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "net_amount": data.net_amount,
            "settlement_type": data.settlement_type,
            "cash_amount": data.cash_amount,
            "bank_amount": data.bank_amount,
            "bank_ref_no": data.bank_ref_no,
            "bank_name": data.bank_name,
            "direction": data.direction
        }
        res_settle = supabase.table("test_transaction_settlements").insert(settle_record).execute()
        new_settle_id = res_settle.data[0]["id"]

        # D. தாள்கள் விவரங்கள் சேமித்தல்
        if data.cash_amount > 0 and data.denominations:
            supabase.table("test_cash_denominations").insert({
                "settlement_id": new_settle_id,
                "c_500": data.denominations.c_500,
                "c_200": data.denominations.c_200,
                "c_100": data.denominations.c_100,
                "c_50": data.denominations.c_50,
                "c_20": data.denominations.c_20,
                "c_10": data.denominations.c_10,
                "c_coins": data.denominations.c_coins,
                "total_calculated_cash": data.cash_amount
            }).execute()

        # E. OTP சரிபார்க்கப்பட்டதாக மாற்றுதல்
        supabase.table("test_transaction_otps").update({"is_verified": True}).eq("id", latest_otp["id"]).execute()

        return {
            "status": "success",
            "message": "🎉 பரிவர்த்தனை வெற்றிகரமாக முடிவடைந்தது! வருகை நிறைவு செய்யப்பட்டது.",
            "settlement_id": new_settle_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"செட்டில்மென்ட் பிழை: {str(e)}")

# 9. நேரடி செட்டில்மென்ட் API (OTP இல்லாத நேரடி முடிவு / Fail-safe)
@app.post("/api/transaction/settle")
def direct_settle_transaction(data: DirectSettlementPayload):
    try:
        if data.cash_amount > 0 and data.denominations:
            calc_cash = (
                data.denominations.c_500 * 500 +
                data.denominations.c_200 * 200 +
                data.denominations.c_100 * 100 +
                data.denominations.c_50 * 50 +
                data.denominations.c_20 * 20 +
                data.denominations.c_10 * 10 +
                data.denominations.c_coins
            )
            if round(calc_cash, 2) != round(data.cash_amount, 2):
                raise HTTPException(
                    status_code=400,
                    detail=f"தாள்களின் கூட்டுத்தொகை (₹{calc_cash}) ரொக்கத் தொகையுடன் (₹{data.cash_amount}) பொருந்தவில்லை."
                )

        settle_record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "net_amount": data.net_amount,
            "settlement_type": data.settlement_type,
            "cash_amount": data.cash_amount,
            "bank_amount": data.bank_amount,
            "bank_ref_no": data.bank_ref_no,
            "bank_name": data.bank_name,
            "direction": data.direction
        }
        res_settle = supabase.table("test_transaction_settlements").insert(settle_record).execute()
        new_settle_id = res_settle.data[0]["id"]

        if data.cash_amount > 0 and data.denominations:
            supabase.table("test_cash_denominations").insert({
                "settlement_id": new_settle_id,
                "c_500": data.denominations.c_500,
                "c_200": data.denominations.c_200,
                "c_100": data.denominations.c_100,
                "c_50": data.denominations.c_50,
                "c_20": data.denominations.c_20,
                "c_10": data.denominations.c_10,
                "c_coins": data.denominations.c_coins,
                "total_calculated_cash": data.cash_amount
            }).execute()

        return {
            "status": "success",
            "message": "✅ பரிவர்த்தனை தீர்வு வெற்றிகரமாகச் சேமிக்கப்பட்டது!",
            "settlement_id": new_settle_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"செட்டில்மென்ட் பிழை: {str(e)}")
