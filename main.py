import os
import random
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from database import supabase

# இந்திய நேர மண்டலம் (IST = UTC + 5 மணி 30 நிமிடங்கள்)
IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(
    title="Muthusise Gold Loan Management - Enterprise Core",
    version="6.6.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

def send_fast2sms_otp(mobile_no: str, otp_code: str, customer_name: str, amount: float, txn_type: str = "receive"):
    try:
        api_key = os.getenv("FAST2SMS_API_KEY", "eBGQYanRZNKVCpMSg3KB5kUxY2QhDnOjxesh3Hqr7FOG792XV9wut4TPhQia")
        clean_mobile = "".join(filter(str.isdigit, str(mobile_no)))[-10:]
        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {
            "authorization": api_key.strip(),
            "Content-Type": "application/x-www-form-urlencoded",
            "accept": "application/json",
        }
        var_values = f"{customer_name}|{abs(amount):,.2f}|{otp_code}"
        dlt_msg_id = "229683" if txn_type == "receive" else "229682"
        payload = {
            "route": "dlt",
            "sender_id": "MUTUSI",
            "message": dlt_msg_id,
            "variables_values": var_values,
            "numbers": clean_mobile,
            "flash": "0"
        }
        resp = requests.post(url, headers=headers, data=payload, timeout=15)
        try:
            res_json = resp.json()
        except Exception:
            return False, f"SMS சர்வர் பிழை (Status {resp.status_code})"

        if res_json.get("return") is True:
            return True, "SMS அனுப்பப்பட்டது!"
        return False, str(res_json.get("message") or res_json)
    except Exception as e:
        return False, f"SMS இணைப்புப் பிழை: {str(e)}"

def send_packet_handover_sms(mobile_no: str, otp_code: str, loan_no: str):
    """நகைக்கடன் பாக்கெட் ஒப்படைப்பிற்கான Fast2SMS DLT OTP (Sender: MTHSEG, Msg ID: 219832)"""
    try:
        api_key = os.getenv("FAST2SMS_API_KEY", "eBGQYanRZNKVCpMSg3KB5kUxY2QhDnOjxesh3Hqr7FOG792XV9wut4TPhQia")
        clean_mobile = "".join(filter(str.isdigit, str(mobile_no)))[-10:]
        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {"authorization": api_key.strip()}
        payload = {
            "sender_id": "MTHSEG",
            "message": "219832",
            "route": "dlt",
            "numbers": clean_mobile,
            "variables_values": f"{otp_code}|{loan_no}"
        }
        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        res_json = resp.json()
        if res_json.get("return") is True:
            return True, "பாக்கெட் ஒப்படைப்பு OTP SMS அனுப்பப்பட்டது!"
        return False, str(res_json.get("message") or res_json)
    except Exception as e:
        return False, f"SMS இணைப்புப் பிழை: {str(e)}"

# ==============================================================================
# 🏆 புள்ளி அடிப்படையிலான பணியாளர் இன்சென்டிவ் இயந்திரம் (STAFF INCENTIVE ENGINE)
# ==============================================================================
def get_active_incentive_settings():
    try:
        res = supabase.table("test_incentive_settings").select("*").eq("id", 1).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {
        "point_value_inr": 10.0,
        "gl_new_per_10k": 1.0,
        "gl_close_per_10k": 1.0,
        "gold_sale_per_gram": 5.0,
        "old_gold_per_gram": 3.0,
        "gss_join_bonus_points": 5.0,
        "gss_per_1k_points": 1.0,
        "rd_join_bonus_points": 5.0,
        "rd_per_1k_points": 1.0,
        "fd_per_10k": 2.0,
    }

def calculate_branch_walkin_shares(branch_id: int):
    staff_res = (
        supabase.table("test_staff_users")
        .select("id, full_name, role_key, is_active, is_branch_manager")
        .eq("branch_id", branch_id)
        .execute()
    )
    active_staff = [s for s in (staff_res.data or []) if s.get("is_active", True) is not False]
    if not active_staff:
        return []

    managers = [
        s for s in active_staff
        if s.get("is_branch_manager") is True or str(s.get("role_key") or "").upper() in ["BRANCH_MANAGER", "MANAGER"]
    ]
    regulars = [s for s in active_staff if s not in managers]

    shares = []
    if len(managers) == 1 and len(regulars) >= 1:
        mgr = managers[0]
        n = len(regulars)
        if n == 1:
            mgr_pct, reg_pct = 60.0, 40.0
        elif n == 2:
            mgr_pct, reg_pct = 50.0, 25.0
        elif n == 3:
            mgr_pct, reg_pct = 40.0, 20.0
        else:
            mgr_pct = 30.0
            reg_pct = round(70.0 / n, 4)

        shares.append({"staff_id": mgr["id"], "staff_name": mgr["full_name"], "pct": mgr_pct})
        for r in regulars:
            shares.append({"staff_id": r["id"], "staff_name": r["full_name"], "pct": reg_pct})
    else:
        equal_pct = round(100.0 / len(active_staff), 4)
        for s in active_staff:
            shares.append({"staff_id": s["id"], "staff_name": s["full_name"], "pct": equal_pct})

    return shares

def record_incentive_points(
    branch_id: int,
    txn_type: str,
    ref_no: str,
    amount_or_grams: float,
    source_staff_id: Optional[int] = None,
    txn_date: Optional[str] = None,
    scheme_id: Optional[int] = None,
    remarks: str = ""
):
    try:
        cfg = get_active_incentive_settings()
        pt_val = float(cfg.get("point_value_inr") or 10.0)
        val = float(amount_or_grams or 0.0)
        total_points = 0.0

        if txn_type == "GL_NEW":
            total_points = (val / 10000.0) * float(cfg.get("gl_new_per_10k") or 1.0)
        elif txn_type in ["GL_PART_PRINCIPAL", "GL_CLOSE"]:
            # கடன் முடிப்பு மற்றும் பகுதி அசல் எப்போதும் Walk-in ஆக மட்டுமே கணக்கிடப்படும்
            source_staff_id = None
            total_points = -1.0 * (val / 10000.0) * float(cfg.get("gl_close_per_10k") or 1.0)
        elif txn_type == "GOLD_SALE":
            total_points = val * float(cfg.get("gold_sale_per_gram") or 5.0)
        elif txn_type == "OLD_GOLD":
            total_points = val * float(cfg.get("old_gold_per_gram") or 3.0)
        elif txn_type == "GSS_JOIN":
            join_pts = float(cfg.get("gss_join_bonus_points") or 5.0)
            amt_pts = (val / 1000.0) * float(cfg.get("gss_per_1k_points") or 1.0)
            total_points = join_pts + amt_pts
        elif txn_type == "GSS_INST":
            total_points = (val / 1000.0) * float(cfg.get("gss_per_1k_points") or 1.0)
        elif txn_type in ["RD_JOIN", "RD_INST"]:
            # குறிப்பிட்ட RD திட்டத்தின் புள்ளிகளை எடுத்தல் (இல்லையெனில் பொது அமைப்பை எடுக்கும்)
            rd_join_pts = float(cfg.get("rd_join_bonus_points") or 5.0)
            rd_1k_pts = float(cfg.get("rd_per_1k_points") or 1.0)
            if scheme_id:
                try:
                    sch_res = supabase.table("test_rd_schemes").select("join_bonus_points, per_1k_points").eq("id", int(scheme_id)).execute()
                    if sch_res.data:
                        if sch_res.data[0].get("join_bonus_points") is not None:
                            rd_join_pts = float(sch_res.data[0]["join_bonus_points"])
                        if sch_res.data[0].get("per_1k_points") is not None:
                            rd_1k_pts = float(sch_res.data[0]["per_1k_points"])
                except Exception:
                    pass

            amt_pts = (val / 1000.0) * rd_1k_pts
            total_points = (rd_join_pts + amt_pts) if txn_type == "RD_JOIN" else amt_pts
            
        elif txn_type == "FD_NEW":
            total_points = (val / 10000.0) * float(cfg.get("fd_per_10k") or 2.0)

        total_points = round(total_points, 4)
        if total_points == 0:
            return

        effective_date = txn_date or datetime.now(IST).strftime("%Y-%m-%d")
        rows_to_insert = []
        if source_staff_id and int(source_staff_id) > 0:
            inc_amt = round(total_points * pt_val, 2)
            rows_to_insert.append({
                "branch_id": branch_id,
                "staff_id": int(source_staff_id),
                "txn_date": effective_date,
                "txn_type": txn_type,
                "ref_no": str(ref_no),
                "source_type": "DIRECT",
                "share_percent": 100.0,
                "points": total_points,
                "point_value_inr": pt_val,
                "incentive_amount": inc_amt,
                "remarks": remarks or f"நேரடி வணிகம் ({txn_type})"
            })
        else:
            shares = calculate_branch_walkin_shares(branch_id)
            for sh in shares:
                staff_pts = round(total_points * (sh["pct"] / 100.0), 4)
                inc_amt = round(staff_pts * pt_val, 2)
                rows_to_insert.append({
                    "branch_id": branch_id,
                    "staff_id": sh["staff_id"],
                    "txn_date": effective_date,
                    "txn_type": txn_type,
                    "ref_no": str(ref_no),
                    "source_type": "WALKIN",
                    "share_percent": sh["pct"],
                    "points": staff_pts,
                    "point_value_inr": pt_val,
                    "incentive_amount": inc_amt,
                    "remarks": remarks or f"Walk-in பகிர்வு ({sh['pct']}%)"
                })

        if rows_to_insert:
            supabase.table("test_staff_incentive_ledger").insert(rows_to_insert).execute()
    except Exception as e:
        print("Incentive Ledger Note:", e)
        
# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class BranchPayload(BaseModel):
    branch_code: str
    branch_name: str
    city: str
    phone: Optional[str] = None

class StaffPayload(BaseModel):
    username: str
    password: Optional[str] = None
    full_name: str
    mobile: str
    role_key: str = "BRANCH_STAFF"
    branch_id: int
    is_active: bool = True
    is_branch_manager: bool = False
    can_access_counter: bool = True
    can_approve_kyc: bool = False
    can_approve_updates: bool = False
    can_manage_users: bool = False
    can_approve_otp_exempt: bool = False
    can_approve_expenses: bool = False  
    can_manage_treasury: bool = False
    can_approve_rebate: bool = False
    can_manage_gp_stock: bool = False
    can_approve_gss_benefit: bool = False
    can_access_hq_packets: bool = False
    can_approve_hq_packets: bool = False
    can_audit_documents: bool = False

class CompanyBankPayload(BaseModel):
    bank_name: str
    branch_name: str
    account_type: str = "CURRENT"
    account_no: str
    ifsc_code: str
    upi_id: Optional[str] = None

class InterestSlab(BaseModel):
    from_days: int
    to_days: int
    rate_percent: float

class LoanSchemePayload(BaseModel):
    scheme_code: str
    scheme_name: str
    min_loan_amount: float = 1000.00
    max_loan_amount: float = 1500000.00
    tenure_months: int = 12
    min_interest_days: int = 7
    auction_grace_days: int = 30
    auction_charge_amount: float = 500.00
    processing_charge_type: str = "PLEDGE"
    processing_charge_calc: str = "AMOUNT"
    processing_charge_value: float = 0.00
    max_ltv_percentage: float = 75.00
    interest_slabs: List[InterestSlab]
    purity_rate_multipliers: Optional[Dict[str, float]] = {
        "916": 0.75, "22CT": 0.75, "18CT": 0.60, "999": 0.85
    }

class DailyGoldRatePayload(BaseModel):
    rate_24k_per_gram: float
    rate_22k_per_gram: float
    rate_18k_per_gram: float

class FullCustomerKYCPayload(BaseModel):
    name: str
    mobile: str
    alt_mobile: Optional[str] = None
    guardian_name: Optional[str] = None
    relation_type: Optional[str] = "தந்தை"
    address: Optional[str] = None
    id_proof_type: Optional[str] = "Aadhaar Card"
    id_proof_no: Optional[str] = None
    nominee_name: Optional[str] = None
    nominee_relation: Optional[str] = None
    nominee_mobile: Optional[str] = None
    ref1_name: Optional[str] = None
    ref1_mobile: Optional[str] = None
    ref1_address: Optional[str] = None
    ref2_name: Optional[str] = None
    ref2_mobile: Optional[str] = None
    ref2_address: Optional[str] = None
    customer_photo: Optional[str] = None
    signature_photo: Optional[str] = None
    id_proof_photo: Optional[str] = None
    branch_id: int = 1

class CustomerVisitEntry(BaseModel):
    customer_id: int
    branch_id: int = 1
    purpose: Optional[str] = "REGULAR_TRANSACTION"
    transaction_date: Optional[str] = None

class CustomerUpdateRequest(BaseModel):
    customer_id: int
    branch_id: int = 1
    requested_changes: Dict[str, Any]

class ApprovalActionPayload(BaseModel):
    request_id: int
    action: str
    admin_id: int

class BankTransferPayload(BaseModel):
    customer_id: int
    branch_id: int = 1
    settlement_id: Optional[int] = None
    direction: str
    amount: float
    pay_mode: str
    beneficiary_name: Optional[str] = None
    account_no: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    upi_id: Optional[str] = None
    is_third_party: bool = False
    passbook_photo: Optional[str] = None
    consent_doc_photo: Optional[str] = None
    company_bank_name: Optional[str] = None
    receipt_ref_no: Optional[str] = None
    receipt_screenshot: Optional[str] = None

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
    direction: str

class SettleWithOtpPayload(BaseModel):
    customer_id: int
    branch_id: int = 1
    visit_id: Optional[int] = None
    otp_code: Optional[str] = None
    is_exempted: bool = False
    net_amount: float
    direction: str
    settlement_type: str
    cash_amount: float = 0.0
    bank_amount: float = 0.0
    bank_ref_no: Optional[str] = None
    bank_name: Optional[str] = None
    denominations: Optional[DenominationCounts] = None
    transaction_date: Optional[str] = None
    actions_summary: Optional[str] = None
    business_source_staff_id: Optional[int] = None
    cart_items: Optional[List[Dict[str, Any]]] = []

class OtpExemptRequestPayload(BaseModel):
    visit_id: int
    branch_id: int
    reason: str
    staff_id: int

class OtpExemptApprovalPayload(BaseModel):
    visit_id: int
    action: str
    admin_id: int

class ExpenseApprovalPayload(BaseModel):
    expense_id: int
    action: str
    admin_id: int

class TreasuryApprovalPayload(BaseModel):
    transfer_id: int
    action: str
    admin_id: int

# ==========================================
# 🏆 இன்சென்டிவ் அமைப்புகள் & அறிக்கை API-கள்
# ==========================================
@app.get("/api/admin/incentive-settings")
def api_get_incentive_settings():
    return {"status": "success", "data": get_active_incentive_settings()}

@app.post("/api/admin/incentive-settings")
def api_save_incentive_settings(data: dict):
    try:
        payload = {
            "point_value_inr": float(data.get("point_value_inr", 10.0)),
            "gl_new_per_10k": float(data.get("gl_new_per_10k", 1.0)),
            "gl_close_per_10k": float(data.get("gl_close_per_10k", 1.0)),
            "gold_sale_per_gram": float(data.get("gold_sale_per_gram", 5.0)),
            "old_gold_per_gram": float(data.get("old_gold_per_gram", 3.0)),
            "gss_join_bonus_points": float(data.get("gss_join_bonus_points", 5.0)),
            "gss_per_1k_points": float(data.get("gss_per_1k_points", 1.0)),
            "rd_join_bonus_points": float(data.get("rd_join_bonus_points", 5.0)),
            "rd_per_1k_points": float(data.get("rd_per_1k_points", 1.0)),
            "fd_per_10k": float(data.get("fd_per_10k", 2.0)),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("test_incentive_settings").update(payload).eq("id", 1).execute()
        return {"status": "success", "message": "இன்சென்டிவ் புள்ளி விதிகள் வெற்றிகரமாகச் சேமிக்கப்பட்டன!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/api/incentive/report")
def api_get_incentive_report(from_date: str = "", to_date: str = "", branch_id: int = 0):
    try:
        q = supabase.table("test_staff_incentive_ledger").select("*").order("id", desc=True)
        if from_date:
            q = q.gte("txn_date", from_date)
        if to_date:
            q = q.lte("txn_date", to_date)
        if branch_id and int(branch_id) > 0:
            q = q.eq("branch_id", int(branch_id))
        res = q.limit(3000).execute()
        rows = res.data or []

        # ✅ ஆடிட் முடிந்த (audit_status == 'AUDITED') வருகைகளை மட்டுமே கண்டறிதல்
        visits_q = supabase.table("test_customer_visits").select("id, customer_id, transaction_date, actions_summary, audit_status").eq("audit_status", "AUDITED")
        if from_date:
            visits_q = visits_q.gte("transaction_date", from_date)
        if to_date:
            visits_q = visits_q.lte("transaction_date", to_date)
        if branch_id and int(branch_id) > 0:
            visits_q = visits_q.eq("branch_id", int(branch_id))
        audited_visits = visits_q.limit(5000).execute().data or []

        # ஆடிட் முடிந்த Ref No / Loan No / Visit / Customer+Date பட்டியலை உருவாக்குதல்
        audited_refs = set()
        audited_cust_dates = set()
        for v in audited_visits:
            if v.get("customer_id") and v.get("transaction_date"):
                audited_cust_dates.add((int(v["customer_id"]), str(v["transaction_date"])))
            for act_item in extract_visit_action_items(v.get("actions_summary") or ""):
                ref_val = str(act_item.get("ref_no") or "").strip().upper()
                if ref_val and ref_val != "-":
                    audited_refs.add(ref_val)

        # கடன் / GP / GS / GSS / RD / SI அட்டவணைகளில் ஆடிட் செய்யப்பட்ட visit_id கொண்ட எண்களைச் சேர்த்தல்
        audited_visit_ids = {v["id"] for v in audited_visits if v.get("id")}
        if audited_visit_ids:
            v_id_list = list(audited_visit_ids)
            for tbl, col in [
                ("test_gold_loans", "loan_no"),
                ("test_gold_purchases", "gp_no"),
                ("test_gold_sales", "gs_no"),
                ("test_customer_savings_accounts", "gss_no"),
                ("test_customer_rd_accounts", "rd_no"),
                ("test_si_accounts", "si_no"),
            ]:
                try:
                    t_rows = supabase.table(tbl).select(col).in_("visit_id", v_id_list).execute().data or []
                    for tr in t_rows:
                        val = str(tr.get(col) or "").strip().upper()
                        if val:
                            audited_refs.add(val)
                except Exception:
                    continue

        filtered_rows = []
        for r in rows:
            ref_no = str(r.get("ref_no") or "").strip().upper()
            matched_by_ref = bool(ref_no and ref_no in audited_refs)
            matched_by_remarks = any(ref_token and ref_token in str(r.get("remarks") or "").upper() for ref_token in audited_refs)
            if matched_by_ref or matched_by_remarks:
                filtered_rows.append(r)

        staff_res = supabase.table("test_staff_users").select("id, full_name, username, role_key, is_active, is_branch_manager").execute().data or []
        s_map = {s["id"]: s for s in staff_res}

        br_res = supabase.table("test_branches").select("id, branch_name").execute().data or []
        b_map = {b["id"]: b.get("branch_name", "-") for b in br_res}

        for r in filtered_rows:
            st_info = s_map.get(r.get("staff_id")) or {
                "full_name": f"Staff #{r.get('staff_id')}",
                "username": "-",
                "role_key": "BRANCH_STAFF",
                "is_active": True,
                "is_branch_manager": False
            }
            r["test_staff_users"] = st_info
            r["branch_name"] = b_map.get(r.get("branch_id"), "-")

        return {"status": "success", "data": filtered_rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"இன்சென்டிவ் அறிக்கை பிழை: {str(e)}")
        
# ==========================================
# 🧾 கிளை தினசரி செலவு மேலாண்மை (Branch Expenses)
# ==========================================
@app.post("/api/expense/request")
def create_branch_expense(data: dict):
    try:
        branch_id = data.get("branch_id") or 1
        trans_date = data.get("transaction_date") or datetime.now(IST).strftime("%Y-%m-%d")

        day_chk = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", branch_id)
            .eq("business_date", trans_date)
            .execute()
        )
        if day_chk.data and day_chk.data[0].get("status") == "CLOSED":
            raise HTTPException(
                status_code=400, 
                detail=f"⚠️ {trans_date} நாளுக்கான மாலை கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது! இந்தப் பழைய தேதியில் புதிய செலவுகளைப் பதிவு செய்ய முடியாது."
            )

        record = {
            "branch_id": branch_id,
            "category": data.get("category"),
            "amount": float(data.get("amount") or 0.0),
            "payment_mode": data.get("payment_mode", "CASH"),
            "reason": data.get("reason"),
            "bill_photo": data.get("bill_photo"),
            "status": "PENDING",
            "created_by": data.get("staff_id"),
            "transaction_date": trans_date,
            "created_at": datetime.now(IST).isoformat()
        }
        res = supabase.table("test_branch_expenses").insert(record).execute()
        return {"status": "success", "message": "செலவுக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது.", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"செலவு பதிவு பிழை: {str(e)}")

@app.get("/api/hq/pending-expenses")
def get_pending_expenses():
    try:
        branch_res = supabase.table("test_branches").select("id, branch_name, branch_code").execute()
        b_map = {b["id"]: b for b in (branch_res.data or [])}

        exp_res = (
            supabase.table("test_branch_expenses")
            .select("*")
            .eq("status", "PENDING")
            .order("id", desc=True)
            .execute()
        )
        data = exp_res.data or []
        for x in data:
            b = b_map.get(x.get("branch_id"), {})
            x["branch_name"] = b.get("branch_name", f"கிளை #{x.get('branch_id')}")

        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-expense")
def approve_branch_expense(data: ExpenseApprovalPayload):
    try:
        status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_branch_expenses").update({
            "status": status,
            "approved_by": data.admin_id,
            "approved_at": "now()"
        }).eq("id", data.expense_id).execute()

        return {"status": "success", "message": f"செலவு வெற்றிகரமாக '{status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API Endpoints
@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI Server Running"}

@app.get("/health")
def health_check():
    return {"status": "active", "service": "Enterprise API v6.6"}

# 1. Staff Login
@app.post("/api/auth/staff-login")
def staff_unified_login(data: LoginRequest):
    try:
        res = (
            supabase.table("test_staff_users")
            .select("*, test_branches(branch_name, branch_code)")
            .eq("username", data.username.strip())
            .eq("password", data.password.strip())
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=401, detail="பயனர் பெயர் அல்லது கடவுச்சொல் தவறானது!")

        user = res.data[0]
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="இந்தக் கணக்கு முடக்கப்பட்டுள்ளது.")

        branch_info = user.get("test_branches") or {}
        role = user.get("role_key", "BRANCH_STAFF")
        is_admin_role = (role in ["HQ_ADMIN", "ADMIN"])

        user_profile = {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role_key": role,
            "branch_id": user.get("branch_id") or 1,
            "branch_code": branch_info.get("branch_code", "BR"),
            "branch_name": branch_info.get("branch_name", "Branch"),
            "is_branch_manager": bool(user.get("is_branch_manager", False)),
            "permissions": {
                "can_access_counter": True if is_admin_role else bool(user.get("can_access_counter", True)),
                "can_approve_kyc": True if is_admin_role else bool(user.get("can_approve_kyc", False)),
                "can_approve_updates": True if is_admin_role else bool(user.get("can_approve_updates", False)),
                "can_manage_users": True if is_admin_role else bool(user.get("can_manage_users", False)),
                "can_approve_otp_exempt": True if is_admin_role else bool(user.get("can_approve_otp_exempt", False)),
                "can_approve_expenses": True if is_admin_role else bool(user.get("can_approve_expenses", False)),
                "can_manage_treasury": True if is_admin_role else bool(user.get("can_manage_treasury", False)),
                "can_approve_rebate": True if is_admin_role else bool(user.get("can_approve_rebate", False)),
                "can_manage_gp_stock": True if is_admin_role else bool(user.get("can_manage_gp_stock", False)),
                "can_approve_gss_benefit": True if is_admin_role else bool(user.get("can_approve_gss_benefit", False)),
                "can_access_hq_packets": bool(user.get("can_access_hq_packets", False)),
                "can_approve_hq_packets": bool(user.get("can_approve_hq_packets", False)),
                "can_audit_documents": True if is_admin_role else bool(user.get("can_audit_documents", False))
            }
        }
        return {"status": "success", "message": "உள்நுழைவு முடிந்தது!", "user": user_profile}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"உள்நுழைவு பிழை: {str(e)}")

# 2. Customer Search
@app.get("/api/customer/search")
def search_customer(query: str = Query(..., min_length=1), branch_id: int = Query(...)):
    try:
        clean_query = query.strip()
        db_query = supabase.table("test_customers").select("*").eq("branch_id", branch_id)
        if clean_query.isdigit():
            res = db_query.ilike("mobile", f"%{clean_query}%").limit(10).execute()
        else:
            res = db_query.ilike("name", f"%{clean_query}%").limit(10).execute()
        return {"status": "success", "count": len(res.data or []), "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")

# 3. Next Loan Number
@app.get("/api/loan/next-loan-no")
def get_next_loan_no(branch_id: int = Query(...)):
    try:
        branch_res = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        if not branch_res.data:
            raise HTTPException(status_code=404, detail="கிளை விபரம் கிடைக்கவில்லை.")
        branch_code = branch_res.data[0]["branch_code"].strip().upper()
        count_res = supabase.table("test_gold_loans").select("id", count="exact").eq("branch_id", branch_id).execute()
        next_count = (count_res.count or len(count_res.data or [])) + 1
        formatted_loan_no = f"{branch_code}/{next_count:04d}"
        return {
            "status": "success",
            "branch_code": branch_code,
            "next_loan_no": formatted_loan_no,
            "count": next_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கடன் எண் பிழை: {str(e)}")
        
@app.get("/api/customer/{customer_id}/active-loans")
def get_customer_active_loans(customer_id: int):
    try:
        # 🔒 நிராகரிக்கப்பட்ட (REJECTED) வருகைகளில் உருவான கடன்கள் 'ACTIVE' ஆக காட்டப்படுவதைத் தடுத்தல்
        try:
            rej_visits = (
                supabase.table("test_customer_visits")
                .select("id")
                .eq("customer_id", customer_id)
                .eq("status", "REJECTED")
                .execute()
                .data or []
            )
            rej_visit_ids = [v["id"] for v in rej_visits if v.get("id")]
            if rej_visit_ids:
                supabase.table("test_gold_loans").update({"status": "CANCELLED"}).eq("customer_id", customer_id).eq("status", "ACTIVE").in_("visit_id", rej_visit_ids).execute()
                supabase.table("test_gold_packets").update({"packet_status": "CANCELLED"}).eq("customer_id", customer_id).in_("visit_id", rej_visit_ids).execute()
                supabase.table("test_gold_purchases").update({"status": "CANCELLED"}).eq("customer_id", customer_id).in_("visit_id", rej_visit_ids).execute()
                supabase.table("test_customer_savings_accounts").update({"status": "CANCELLED"}).eq("customer_id", customer_id).eq("status", "ACTIVE").in_("visit_id", rej_visit_ids).execute()
                supabase.table("test_customer_rd_accounts").update({"status": "CANCELLED"}).eq("customer_id", customer_id).eq("status", "ACTIVE").in_("visit_id", rej_visit_ids).execute()
                supabase.table("test_si_accounts").update({"status": "CANCELLED"}).eq("customer_id", customer_id).eq("status", "ACTIVE").in_("visit_id", rej_visit_ids).execute()
        except Exception as sync_err:
            print("Rejected visit cleanup note:", sync_err)

        res = supabase.table("test_gold_loans") \
            .select("*, test_gold_loan_items(*)") \
            .eq("customer_id", customer_id) \
            .eq("status", "ACTIVE") \
            .order("id", desc=False) \
            .execute()
        
        loans = res.data or []
        for loan in loans:
            history = []
            for tbl_name in ["test_gold_loan_repayments", "test_gold_loan_transactions", "test_loan_repayments"]:
                try:
                    h_res = supabase.table(tbl_name) \
                        .select("*") \
                        .eq("loan_id", loan["id"]) \
                        .order("id", desc=False) \
                        .execute()
                    if h_res.data:
                        history = h_res.data
                        break
                except Exception:
                    continue
            loan["repayment_history"] = history

        return {"status": "success", "data": loans}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. New Gold Loan
@app.post("/api/loan/new-pawn")
def create_new_pawn(data: dict):
    try:
        branch_id = data.get("branch_id") or 1
        trans_date = data.get("transaction_date") or datetime.now(IST).strftime("%Y-%m-%d")

        check_day = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", branch_id)
            .eq("business_date", trans_date)
            .execute()
        )
        if check_day.data and check_day.data[0].get("status") == "CLOSED":
            raise HTTPException(status_code=400, detail="இந்த நாளுக்கான கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED). புதிய அடகு வைக்க முடியாது!")

        items = data.get("items") or []
        if not items:
            raise HTTPException(status_code=400, detail="நகைகளைச் சேர்க்கவும்.")

        total_gross = sum(float(i.get("gross_weight") if isinstance(i, dict) else getattr(i, "gross_weight", 0) or 0) for i in items)
        total_net = sum(float(i.get("net_weight") if isinstance(i, dict) else getattr(i, "net_weight", 0) or 0) for i in items)
        
        loan_amt = float(data.get("loan_amount") or 0.0)
        charges_amt = float(data.get("charges_amount") or 0.0)
        net_payable = loan_amt - charges_amt
        ornament_img = data.get("ornament_photo") or data.get("photo_url")
        loan_no_clean = str(data.get("loan_no") or "").strip()

        loan_record = {
            "loan_no": loan_no_clean,
            "customer_id": data.get("customer_id"),
            "scheme_name": data.get("scheme_name"),
            "total_gross_weight": round(total_gross, 3),
            "total_net_weight": round(total_net, 3),
            "loan_amount": loan_amt,
            "charges_amount": charges_amt,
            "net_payable_amount": net_payable,
            "photo_url": ornament_img,
            "ornament_photo": ornament_img,
            "branch_id": branch_id,
            "status": "ACTIVE",
            "visit_id": data.get("visit_id"),
            "transaction_date": trans_date,
            "outstanding_principal": loan_amt,
            "last_interest_paid_date": trans_date,
            "created_at": datetime.now(IST).isoformat()
        }
        res_loan = supabase.table("test_gold_loans").insert(loan_record).execute()
        if not res_loan.data:
            raise HTTPException(status_code=500, detail="கடன் பதிவு தோல்வியடைந்தது.")
        new_loan_id = res_loan.data[0]["id"]

        items_payload = []
        for i in items:
            if isinstance(i, dict):
                items_payload.append({
                    "loan_id": new_loan_id,
                    "item_type": str(i.get("item_type") or "").strip(),
                    "item_count": int(i.get("item_count") or 1),
                    "gross_weight": float(i.get("gross_weight") or 0.0),
                    "net_weight": float(i.get("net_weight") or 0.0),
                    "purity": i.get("purity")
                })
            else:
                items_payload.append({
                    "loan_id": new_loan_id,
                    "item_type": str(getattr(i, "item_type", "")).strip(),
                    "item_count": int(getattr(i, "item_count", 1)),
                    "gross_weight": float(getattr(i, "gross_weight", 0.0)),
                    "net_weight": float(getattr(i, "net_weight", 0.0)),
                    "purity": getattr(i, "purity", None)
                })

        supabase.table("test_gold_loan_items").insert(items_payload).execute()
        return {"status": "success", "message": "நகைக்கடன் கார்ட்டில் சேர்க்கப்பட்டது.", "loan_id": new_loan_id, "net_payable": net_payable}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கடன் உருவாக்கம் பிழை: {str(e)}")

# நாள் நிலையைச் சரிபார்த்தல்
@app.get("/api/cash-day/status")
def get_cash_day_status(branch_id: int, date: Optional[str] = None, date_str: Optional[str] = None):
    try:
        target_date = date or date_str or datetime.now(IST).strftime("%Y-%m-%d")

        res = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .eq("business_date", target_date)
            .execute()
        )

        if res.data and len(res.data) > 0:
            row = res.data[0]
            is_closed = (row.get("status") == "CLOSED")
            return {
                "status": "success",
                "business_date": target_date,
                "opening_balance": float(row.get("opening_balance") or 0.0),
                "is_closed": is_closed,
                "data": row
            }

        prev_day = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .lt("business_date", target_date)
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )

        auto_opening = 0.0
        if prev_day.data:
            auto_opening = float(prev_day.data[0].get("closing_balance") or prev_day.data[0].get("opening_balance") or 0.0)

        ins_res = supabase.table("test_branch_cash_days").insert({
            "branch_id": branch_id,
            "business_date": target_date,
            "opening_balance": auto_opening,
            "status": "OPEN",
            "created_at": datetime.now(IST).isoformat()
        }).execute()

        new_row = ins_res.data[0] if ins_res.data else None
        return {
            "status": "success",
            "business_date": target_date,
            "opening_balance": auto_opening,
            "is_closed": False,
            "data": new_row
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"நாள் நிலை அறியும் பிழை: {str(e)}")

# 6. Day Report
@app.get("/api/cash-day/report")
def get_cash_day_report(branch_id: int, date_str: str):
    try:
        branch_name = "Aundivilai"
        try:
            br_res = supabase.table("test_branches").select("branch_name").eq("id", branch_id).execute()
            if br_res.data and br_res.data[0].get("branch_name"):
                branch_name = br_res.data[0].get("branch_name")
        except Exception:
            pass

        opening_bal = 0.0
        try:
            prev_closed = (
                supabase.table("test_branch_cash_days")
                .select("closing_balance")
                .eq("branch_id", branch_id)
                .lt("business_date", date_str)
                .eq("status", "CLOSED")
                .order("business_date", desc=True)
                .limit(1)
                .execute()
            )
            if prev_closed.data:
                opening_bal = float(prev_closed.data[0].get("closing_balance") or 0.0)
        except Exception as e:
            print("Opening balance fetch err:", e)

        unified_entries = []
        tot_cash_in = 0.0
        tot_cash_out = 0.0
        tot_bank_in = 0.0
        tot_bank_out = 0.0

        all_visits = []
        try:
            v_res = supabase.table("test_customer_visits").select("*").eq("branch_id", branch_id).eq("status", "VERIFIED").execute()
            for row in (v_res.data or []):
                r_date = str(row.get("transaction_date") or "")
                c_date = str(row.get("created_at") or "")[:10]
                if r_date == date_str or c_date == date_str:
                    all_visits.append(row)
        except Exception as v_err:
            print("Visits fetch error:", v_err)

        cust_ids = [v["customer_id"] for v in all_visits if v.get("customer_id")]
        cust_map = {}
        if cust_ids:
            try:
                c_res = supabase.table("test_customers").select("id, name, mobile").in_("id", cust_ids).execute()
                for c in (c_res.data or []):
                    cust_map[c["id"]] = c
            except Exception:
                pass

        for v in all_visits:
            cid = v.get("customer_id")
            cust_info = cust_map.get(cid, {})
            c_name = cust_info.get("name") or "வாடிக்கையாளர்"
            v_id_val = v.get("id")
            v_code = f"VST-AUN-{int(v_id_val):04d}" if str(v_id_val).isdigit() else f"VST-{v_id_val}"

            net_amt = float(v.get("net_amount") or 0.0)
            cash_val = float(v.get("cash_amount") or 0.0)
            bank_val = float(v.get("bank_amount") or 0.0)
            direction = str(v.get("direction") or "OUTWARD").upper()

            if cash_val == 0.0 and bank_val == 0.0 and net_amt > 0.0:
                cash_val = net_amt

            c_in = c_out = b_in = b_out = 0.0
            if direction in ["OUTWARD", "COMPANY_PAYABLE"]:
                c_out = cash_val
                b_out = bank_val
                tot_cash_out += cash_val
                tot_bank_out += bank_val
            else:
                c_in = cash_val
                b_in = bank_val
                tot_cash_in += cash_val
                tot_bank_in += bank_val

            created_t = str(v.get("created_at") or "")
            t_str = created_t[11:16] if len(created_t) >= 16 else "--:--"

            unified_entries.append({
                "time": t_str,
                "visit_no": v_code,
                "entry_type": "வணிக வருகை",
                "party_name": c_name,
                "activity": v.get("actions_summary") or "Pledge (புதிய நகைக் கடன்)",
                "gross_in": (c_in + b_in) if (c_in + b_in) > 0 else 0.0,
                "gross_out": (c_out + b_out) if (c_out + b_out) > 0 else 0.0,
                "cash_change": (-c_out) if c_out > 0 else (c_in if c_in > 0 else 0.0),
                "bank_change": (-b_out) if b_out > 0 else (b_in if b_in > 0 else 0.0),
                "raw_time": created_t or str(v_id_val)
            })

        try:
            exp_res = supabase.table("test_branch_expenses").select("*").eq("branch_id", branch_id).eq("status", "APPROVED").execute()
            for e in (exp_res.data or []):
                e_date = str(e.get("transaction_date") or "")
                e_created = str(e.get("created_at") or "")[:10]
                if e_date == date_str or e_created == date_str:
                    amt = float(e.get("amount") or 0.0)
                    e_mode = str(e.get("payment_mode") or "CASH").upper()
                    e_time = str(e.get("created_at") or "")
                    t_str = e_time[11:16] if len(e_time) >= 16 else "--:--"
                    if e_mode == "CASH":
                        tot_cash_out += amt
                        c_chg, b_chg = -amt, 0.0
                    else:
                        tot_bank_out += amt
                        c_chg, b_chg = 0.0, -amt

                    unified_entries.append({
                        "time": t_str,
                        "visit_no": "-",
                        "entry_type": "கிளை செலவு",
                        "party_name": e.get("category", "செலவு"),
                        "activity": e.get("reason") or "அங்கீகரிக்கப்பட்ட செலவு",
                        "gross_in": 0.0,
                        "gross_out": amt,
                        "cash_change": c_chg,
                        "bank_change": b_chg,
                        "raw_time": e_time
                    })
        except Exception as e_err:
            print("Expenses report err:", e_err)

        try:
            tr_res = supabase.table("test_treasury_transfers").select("*").eq("branch_id", branch_id).eq("status", "APPROVED").execute()
            type_names = {
                'BRANCH_TO_HQ': ('HQ பணப் பட்டுவாடா', 'கிளை ➔ தலைமை அலுவலகம்'),
                'HQ_TO_BRANCH': ('HQ நிதி ஒதுக்கீடு', 'தலைமையக நிதி வரவு'),
                'CASH_TO_BANK': ('வங்கி டெபாசிட்', 'ரொக்கம் ➔ வங்கி'),
                'BANK_TO_CASH': ('வங்கி வித்ராயல்', 'வங்கி ➔ கிளை ரொக்கம்')
            }
            for t in (tr_res.data or []):
                t_date = str(t.get("transaction_date") or "")
                t_created = str(t.get("created_at") or "")[:10]
                if t_date == date_str or t_created == date_str:
                    amt = float(t.get("amount") or 0.0)
                    ttype = t.get("transfer_type")
                    t_time = str(t.get("created_at") or "")
                    t_str = t_time[11:16] if len(t_time) >= 16 else "--:--"
                    t_title, t_desc = type_names.get(ttype, ('பணப் பரிமாற்றம்', ttype))

                    if ttype in ['HQ_TO_BRANCH', 'BANK_TO_CASH']:
                        tot_cash_in += amt
                        c_chg, g_in, g_out = amt, amt, 0.0
                    else:
                        tot_cash_out += amt
                        c_chg, g_in, g_out = -amt, 0.0, amt

                    unified_entries.append({
                        "time": t_str,
                        "visit_no": "-",
                        "entry_type": t_title,
                        "party_name": t.get("carrier_person") or "பணப் பரிமாற்றம்",
                        "activity": t_desc,
                        "gross_in": g_in,
                        "gross_out": g_out,
                        "cash_change": c_chg,
                        "bank_change": 0.0,
                        "raw_time": t_time
                    })
        except Exception as t_err:
            print("Treasury report err:", t_err)

        unified_entries.sort(key=lambda x: str(x.get("raw_time") or ""))
        calc_closing = opening_bal + tot_cash_in - tot_cash_out

        return {
            "status": "success",
            "branch_name": branch_name,
            "opening_balance": opening_bal,
            "total_cash_in": tot_cash_in,
            "total_cash_out": tot_cash_out,
            "total_bank_in": tot_bank_in,
            "total_bank_out": tot_bank_out,
            "calculated_closing": calc_closing,
            "entries": unified_entries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"அறிக்கை கணக்கீட்டுப் பிழை: {str(e)}")

@app.get("/api/cash-day/next-business-date")
def get_next_business_date(branch_id: int):
    try:
        last_closed = (
            supabase.table("test_branch_cash_days")
            .select("business_date")
            .eq("branch_id", branch_id)
            .eq("status", "CLOSED")
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )
        if last_closed.data:
            last_date_str = last_closed.data[0]["business_date"]
            last_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
            next_date = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            return {"status": "success", "suggested_date": next_date, "last_closed_date": last_date_str}
        else:
            today_str = datetime.now(IST).strftime("%Y-%m-%d")
            return {"status": "success", "suggested_date": today_str, "last_closed_date": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேதி அறிவதில் பிழை: {str(e)}")

@app.get("/api/cash-day/validate-date-sequence")
def validate_date_sequence(branch_id: int, selected_date: str):
    try:
        last_closed = (
            supabase.table("test_branch_cash_days")
            .select("business_date")
            .eq("branch_id", branch_id)
            .eq("status", "CLOSED")
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )
        if last_closed.data:
            last_date_str = last_closed.data[0]["business_date"]
            last_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
            allowed_dt = last_dt + timedelta(days=1)
            allowed_date_str = allowed_dt.strftime("%Y-%m-%d")
            sel_dt = datetime.strptime(selected_date, "%Y-%m-%d")
            if sel_dt > allowed_dt:
                return {
                    "is_valid": False,
                    "allowed_date": allowed_date_str,
                    "message": f"⚠️ தொடர் நாள் விதிமீறல்: {last_date_str} நாளுக்குப் பிறகு அடுத்த வேலை நாளான {allowed_date_str}-ஐ மட்டுமே முடிக்க முடியும்."
                }
        return {"is_valid": True, "message": "அனுமதிக்கப்பட்டது"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cash-day/close")
def close_cash_day(data: dict):
    try:
        branch_id = data.get("branch_id") or 1
        business_date = data.get("business_date") or datetime.now(IST).strftime("%Y-%m-%d")
        closing_balance = float(data.get("closing_balance") or 0.0)
        calc_sys_cash = float(data.get("calculated_system_cash") or 0.0)
        staff_id = data.get("staff_id") or 1
        denoms = data.get("denominations") or {}
        # 🔒 தலைமையக ஒப்புதல் நிலுவை (Pending) இருந்தால் மாலை கணக்கு முடிக்கத் தடை
        pend_v = supabase.table("test_customer_visits").select("id").eq("branch_id", branch_id).eq("transaction_date", business_date).eq("status", "PENDING_HQ").execute().data or []
        pend_e = supabase.table("test_branch_expenses").select("id").eq("branch_id", branch_id).eq("transaction_date", business_date).eq("status", "PENDING").execute().data or []
        pend_t = supabase.table("test_treasury_transfers").select("id").eq("branch_id", branch_id).eq("transaction_date", business_date).eq("status", "PENDING").execute().data or []

        if pend_v or pend_e or pend_t:
            raise HTTPException(
                status_code=400,
                detail=f"⚠️ {business_date} தேதியில் தலைமையக ஒப்புதல் நிலுவையில் உள்ளது! (வருகை: {len(pend_v)}, செலவு: {len(pend_e)}, பணப் பரிமாற்றம்: {len(pend_t)}). முதலில் பென்டிங்கைச் சரிசெய்த பின் மாலை கணக்கு முடிக்கவும்."
            )

        diff = round(closing_balance - calc_sys_cash, 2)
        if diff != 0.0:
            raise HTTPException(
                status_code=400, 
                detail=f"கணினியின்படி இருக்க வேண்டிய ரொக்கமும் (₹{calc_sys_cash:,.2f}) தாள்களின் தொகையும் (₹{closing_balance:,.2f}) சமமாக இல்லை!"
            )

        opening = 0.0
        try:
            prev_day_res = (
                supabase.table("test_branch_cash_days")
                .select("closing_balance, opening_balance")
                .eq("branch_id", branch_id)
                .lt("business_date", business_date)
                .order("business_date", desc=True)
                .limit(1)
                .execute()
            )
            if prev_day_res.data:
                opening = float(prev_day_res.data[0].get("closing_balance") or prev_day_res.data[0].get("opening_balance") or 0.0)
        except Exception as pe:
            print("Previous closing balance fetch error:", pe)

        day_res = (
            supabase.table("test_branch_cash_days")
            .select("id, status")
            .eq("branch_id", branch_id)
            .eq("business_date", business_date)
            .execute()
        )

        if day_res.data and day_res.data[0].get("status") == "CLOSED":
            raise HTTPException(status_code=400, detail=f"{business_date} நாளுக்கான கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED).")

        now_time = datetime.now(IST).isoformat()
        if day_res.data:
            day_id = day_res.data[0]["id"]
            supabase.table("test_branch_cash_days").update({
                "closing_balance": closing_balance,
                "calculated_system_cash": calc_sys_cash,
                "status": "CLOSED",
                "closed_by": staff_id,
                "closed_at": now_time
            }).eq("id", day_id).execute()
        else:
            supabase.table("test_branch_cash_days").insert({
                "branch_id": branch_id,
                "business_date": business_date,
                "opening_balance": opening,
                "closing_balance": closing_balance,
                "calculated_system_cash": calc_sys_cash,
                "status": "CLOSED",
                "opened_by": staff_id,
                "closed_by": staff_id,
                "created_at": now_time,
                "closed_at": now_time
            }).execute()

        if denoms:
            try:
                supabase.table("test_cash_denominations").insert({
                    "branch_id": branch_id,
                    "business_date": business_date,
                    "record_type": "DAY_CLOSE",
                    "c_500": denoms.get("c_500", 0),
                    "c_200": denoms.get("c_200", 0),
                    "c_100": denoms.get("c_100", 0),
                    "c_50": denoms.get("c_50", 0),
                    "c_20": denoms.get("c_20", 0),
                    "c_10": denoms.get("c_10", 0),
                    "c_coins": denoms.get("c_coins", 0),
                    "total_amount": closing_balance
                }).execute()
            except Exception:
                pass

        return {
            "status": "success",
            "message": f"{business_date} மாலை கணக்கு வெற்றிகரமாக முடிக்கப்பட்டு லாக் செய்யப்பட்டது!",
            "closing_balance": closing_balance,
            "difference": 0.0
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"மாலை கணக்கு முடிப்பதில் பிழை: {str(e)}")

# 8. Counter Live Visits Table
@app.get("/api/customer/branch-visits")
def get_branch_visits(branch_id: int = Query(...), date: str = Query(...)):
    try:
        visits_res = (
            supabase.table("test_customer_visits")
            .select("*, test_customers(name, mobile)")
            .eq("branch_id", branch_id)
            .order("id", desc=True)
            .limit(30)
            .execute()
        )
        return {"status": "success", "data": visits_res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    try:
        selected_date = getattr(data, 'transaction_date', None) or datetime.now(IST).strftime("%Y-%m-%d")
        now_ist = datetime.now(IST).isoformat()

        day_check = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", data.branch_id)
            .eq("business_date", selected_date)
            .execute()
        )
        if day_check.data and day_check.data[0].get("status") == "CLOSED":
            raise HTTPException(
                status_code=400, 
                detail=f"தேதி {selected_date}-க்கான மாலை கணக்கு முடிக்கப்பட்டுவிட்டது (Day Closed)."
            )

        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "purpose": data.purpose,
            "transaction_date": selected_date,
            "created_at": now_ist,
            "status": "IN_PROGRESS",
            "audit_status": "PENDING",
            "otp_exemption_status": "NONE",
            "otp_exempted": False
        }
        res = supabase.table("test_customer_visits").insert(record).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="வருகைப் பதிவு தோல்வியடைந்தது.")
        return {"status": "success", "message": "வருகை துவங்கியது.", "data": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வருகைப் பதிவு பிழை: {str(e)}")

# 9. OTP Exemption System
@app.post("/api/otp/request-exemption")
def request_otp_exemption(data: OtpExemptRequestPayload):
    try:
        supabase.table("test_customer_visits").update({
            "otp_exemption_status": "REQUESTED",
            "purpose": f"OTP விலக்குக் கோரிக்கை: {data.reason}"
        }).eq("id", data.visit_id).execute()
        return {"status": "success", "message": "OTP விலக்குக் கோரிக்கை தலைமையகத்திற்கு அனுப்பப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"விலக்குக் கோரிக்கை பிழை: {str(e)}")

@app.get("/api/hq/pending-otp-exemptions")
def get_pending_otp_exemptions():
    try:
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        cust_map = {c["id"]: c for c in (cust_res.data or [])}

        res = (
            supabase.table("test_customer_visits")
            .select("*")
            .eq("otp_exemption_status", "REQUESTED")
            .order("id", desc=True)
            .execute()
        )
        visits_data = res.data or []
        for v in visits_data:
            c = cust_map.get(v.get("customer_id"), {})
            v["test_customers"] = {
                "name": c.get("name", f"வாடிக்கையாளர் #{v.get('customer_id')}"),
                "mobile": c.get("mobile", "-")
            }
        return {"status": "success", "data": visits_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OTP விலக்கு பட்டியல் பிழை: {str(e)}")

@app.get("/api/hq/visit-details/{visit_id}")
def get_visit_details_for_hq(visit_id: int):
    try:
        visit_res = supabase.table("test_customer_visits").select("*").eq("id", visit_id).execute()
        if not visit_res.data:
            raise HTTPException(status_code=404, detail="வருகை விபரம் கிடைக்கவில்லை")
        visit = visit_res.data[0]

        cust_res = supabase.table("test_customers").select("*").eq("id", visit["customer_id"]).execute()
        customer = cust_res.data[0] if cust_res.data else {}

        branch_res = supabase.table("test_branches").select("branch_name, branch_code").eq("id", visit.get("branch_id", 1)).execute()
        branch = branch_res.data[0] if branch_res.data else {}

        v_net_amt = float(visit.get("net_amount") or 0.0)
        loans_query = (
            supabase.table("test_gold_loans")
            .select("*, test_gold_loan_items(*)")
            .eq("customer_id", visit["customer_id"])
        )
        if visit.get("created_at"):
            loans_query = loans_query.gte("created_at", visit["created_at"])
        raw_loans = loans_query.order("id", desc=True).limit(5).execute().data or []

        matched_loans = []
        if raw_loans:
            for l in raw_loans:
                l_amt = float(l.get("loan_amount") or 0.0)
                l_net = float(l.get("net_payable_amount") or 0.0)
                if v_net_amt > 0 and (abs(l_amt - v_net_amt) < 1000 or abs(l_net - v_net_amt) < 1000):
                    matched_loans = [l]
                    break
            if not matched_loans:
                matched_loans = [raw_loans[0]]

        settle_res = (
            supabase.table("test_transaction_settlements")
            .select("*, test_cash_denominations(*)")
            .eq("customer_id", visit["customer_id"])
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        settlement = settle_res.data[0] if settle_res.data else {}

        otp_res = (
            supabase.table("test_transaction_otps")
            .select("*")
            .eq("customer_id", visit["customer_id"])
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        otp_info = otp_res.data[0] if otp_res.data else {}

        return {
            "status": "success",
            "visit": visit,
            "customer": customer,
            "branch": branch,
            "loans": matched_loans,
            "settlement": settlement,
            "otp_info": otp_info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/api/hq/approve-otp-exemption")
def approve_otp_exemption(data: OtpExemptApprovalPayload):
    try:
        status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_customer_visits").update({
            "otp_exemption_status": status,
            "otp_exempted": (status == "APPROVED")
        }).eq("id", data.visit_id).execute()
        return {"status": "success", "message": f"OTP விலக்கு '{status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/otp/exemption-status")
def check_otp_exemption_status(visit_id: int = Query(...)):
    try:
        res = supabase.table("test_customer_visits").select("otp_exemption_status, otp_exempted").eq("id", visit_id).execute()
        if res.data:
            return {"status": "success", "data": res.data[0]}
        return {"status": "success", "data": {"otp_exemption_status": "NONE", "otp_exempted": False}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 10. Settle with OTP (+ Automatic Gold Packet Lifecycle & Staff Incentive Integration)
@app.post("/api/otp/send")
def trigger_otp_sms(payload: SendOtpPayload):
    cust_chk = supabase.table("test_customers").select("kyc_status").eq("id", payload.customer_id).execute()
    if not cust_chk.data or cust_chk.data[0].get("kyc_status") != "VERIFIED":
        raise HTTPException(status_code=403, detail="⚠️ வாடிக்கையாளரின் KYC சரிபார்ப்பு இன்னும் முடியவில்லை (PENDING)! தலைமையக ஒப்புதலுக்குப் பிறகே OTP அனுப்ப முடியும்.")
    otp_code = str(random.randint(100000, 999999))
    txn_type = "receive" if payload.direction == "COMPANY_PAYABLE" else "pay"
    success, msg = send_fast2sms_otp(payload.mobile, otp_code, payload.customer_name, payload.net_amount, txn_type)
    if not success:
        raise HTTPException(status_code=502, detail=f"SMS பிழை: {msg}")
    supabase.table("test_transaction_otps").insert({
        "customer_id": payload.customer_id,
        "mobile": payload.mobile,
        "otp_code": otp_code,
        "net_amount": payload.net_amount,
        "txn_type": txn_type,
        "is_verified": False
    }).execute()
    return {"status": "success", "message": "OTP SMS அனுப்பப்பட்டது."}

@app.post("/api/transaction/settle-with-otp")
def settle_with_otp(data: SettleWithOtpPayload):
    try:
        txn_date = data.transaction_date or datetime.now(IST).strftime("%Y-%m-%d")
        day_status_res = supabase.table("test_branch_cash_days").select("status").eq("branch_id", data.branch_id).eq("business_date", txn_date).execute()
        if day_status_res.data and day_status_res.data[0]["status"] == "CLOSED":
            raise HTTPException(status_code=400, detail="தேர்வு செய்யப்பட்ட நாள் ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED). இதில் பணப் பரிவர்த்தனை செய்ய முடியாது!")

        for item in (data.cart_items or []):
            if item.get("is_repayment") is True:
                meta = item.get("repayment_meta") or {}
                disc_amt = float(meta.get("discount_amount", 0))
                req_id = item.get("rebate_req_id")
                if disc_amt > 0:
                    if not req_id:
                        raise HTTPException(status_code=400, detail="பாதுகாப்புப் பிழை: வட்டி தள்ளுபடி கோரிக்கை எண் (Rebate ID) காணப்படவில்லை!")
                    rebate_check = supabase.table("test_rebate_approvals").select("status").eq("id", req_id).execute()
                    if not rebate_check.data or rebate_check.data[0].get("status") != "APPROVED":
                        raise HTTPException(status_code=400, detail="❌ பரிவர்த்தனை நிராகரிக்கப்பட்டது: வட்டி தள்ளுபடிக்குத் தலைமையக ஒப்புதல் கிடைக்கவில்லை!")

        if not data.is_exempted:
            otp_query = (
                supabase.table("test_transaction_otps")
                .select("id, otp_code, is_verified")
                .eq("customer_id", data.customer_id)
                .eq("is_verified", False)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if not otp_query.data or otp_query.data[0]["otp_code"] != (data.otp_code or "").strip():
                raise HTTPException(status_code=400, detail="OTP தவறானது அல்லது காலாவதியானது.")
            supabase.table("test_transaction_otps").update({"is_verified": True}).eq("id", otp_query.data[0]["id"]).execute()

        settle_record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "net_amount": data.net_amount,
            "settlement_type": data.settlement_type,
            "cash_amount": data.cash_amount,
            "bank_amount": data.bank_amount,
            "bank_ref_no": data.bank_ref_no,
            "bank_name": data.bank_name,
            "direction": data.direction,
            "transaction_date": txn_date
        }
        res_settle = supabase.table("test_transaction_settlements").insert(settle_record).execute()
        if not res_settle.data:
            raise HTTPException(status_code=500, detail="பரிவர்த்தனை பதிவு தோல்வியடைந்தது.")
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

        target_visit_id = data.visit_id
        if not target_visit_id:
            last_visit = (
                supabase.table("test_customer_visits")
                .select("id")
                .eq("customer_id", data.customer_id)
                .eq("branch_id", data.branch_id)
                .order("id", desc=True)
                .limit(1)
                .execute()
            )
            if last_visit.data:
                target_visit_id = last_visit.data[0]["id"]

        if target_visit_id:
            supabase.table("test_customer_visits").update({
                "status": "PENDING_HQ",
                "net_amount": data.net_amount,
                "cash_amount": data.cash_amount,
                "bank_amount": data.bank_amount,
                "direction": data.direction,
                "actions_summary": data.actions_summary or "நகைக்கடன் பரிவர்த்தனை நிறைவுற்றது"
            }).eq("id", target_visit_id).execute()

        default_src_staff = data.business_source_staff_id

        for item in (data.cart_items or []):
            item_src_staff = item.get("business_source_staff_id") or default_src_staff

            # 🔐 0. புதிய அடகுக் கடனுக்கு OTP சரிபார்க்கப்பட்டவுடன் பாக்கெட் உருவாக்குதல் + இன்சென்டிவ் புள்ளிகள் (+)
            if not item.get("is_repayment") and not item.get("is_gold_purchase") and not item.get("is_gold_sale") and not item.get("is_gss_account") and not item.get("is_rd_account") and not item.get("is_si_account") and item.get("loan_no"):
                try:
                    l_no = str(item.get("loan_no")).strip()
                    l_id = item.get("loan_id")
                    exist_pkt = supabase.table("test_gold_packets").select("id").eq("loan_no", l_no).execute()
                    if not exist_pkt.data:
                        pkt_ins = supabase.table("test_gold_packets").insert({
                            "loan_id": l_id,
                            "loan_no": l_no,
                            "customer_id": data.customer_id,
                            "branch_id": data.branch_id,
                            "packet_status": "AT_BRANCH_NEW",
                            "current_location": "BRANCH",
                            "is_loan_closed": False,
                            "is_handed_over": False,
                            "audit_notes": "புதிய அடகு OTP சரிபார்க்கப்பட்டு கிளையில் பாக்கெட் உருவாக்கப்பட்டது"
                        }).execute()
                        if pkt_ins.data:
                            supabase.table("test_gold_packet_movements").insert({
                                "packet_id": pkt_ins.data[0]["id"],
                                "loan_no": l_no,
                                "action_type": "PACKET_CREATED_AT_BRANCH",
                                "from_location": "CUSTOMER",
                                "to_location": "BRANCH",
                                "remarks": "புதிய நகைக்கடன் அடகு மூலம் பாக்கெட் உருவாக்கப்பட்டது"
                            }).execute()

                    # 🏆 புதிய நகைக்கடன் இன்சென்டிவ் புள்ளிகள் (+)
                    loan_amt_val = float(item.get("loan_amount") or 0)
                    if loan_amt_val <= 0 and l_id:
                        l_chk = supabase.table("test_gold_loans").select("loan_amount").eq("id", l_id).execute()
                        if l_chk.data:
                            loan_amt_val = float(l_chk.data[0].get("loan_amount") or 0)
                    if loan_amt_val > 0:
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="GL_NEW",
                            ref_no=l_no,
                            amount_or_grams=loan_amt_val,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            remarks=f"புதிய நகைக்கடன் ({l_no}) - ₹{loan_amt_val:,.0f}"
                        )
                except Exception as pkt_err:
                    print("Packet/Incentive creation note:", pkt_err)

            if item.get("is_repayment") is True:
                loan_id = item.get("loan_id")
                action_type = item.get("action_type")
                meta = item.get("repayment_meta") or {}

                int_paid = float(meta.get("interest_paid", 0))
                prin_paid = float(meta.get("principal_paid", 0))
                disc_amt = float(meta.get("discount_amount", 0))

                supabase.table("test_loan_repayments").insert({
                    "visit_id": target_visit_id,
                    "loan_id": loan_id,
                    "customer_id": data.customer_id,
                    "branch_id": data.branch_id,
                    "action_type": action_type,
                    "interest_paid": int_paid,
                    "principal_paid": prin_paid,
                    "discount_amount": disc_amt,
                    "other_charges": float(meta.get("other_charges", 0)),
                    "auction_notice_charges": float(meta.get("auction_charges", 0)),
                    "days_calculated": meta.get("days_calculated", 0),
                    "rate_applied": meta.get("rate_applied", 0),
                    "transaction_date": txn_date
                }).execute()

                loan_res = supabase.table("test_gold_loans").select("*").eq("id", loan_id).execute()
                if loan_res.data:
                    loan_row = loan_res.data[0]
                    curr_prin = float(loan_row.get("outstanding_principal") or loan_row.get("loan_amount") or 0)
                    new_prin = max(0.0, curr_prin - prin_paid)

                    # 🏆 பகுதி அசல் வசூல் / கடன் முடிப்பு இன்சென்டிவ் புள்ளிகள் கழித்தல் (-)
                    if prin_paid > 0:
                        inc_code = "GL_CLOSE" if (action_type == "FULL_CLOSURE" or new_prin <= 0) else "GL_PART_PRINCIPAL"
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type=inc_code,
                            ref_no=loan_row.get("loan_no", str(loan_id)),
                            amount_or_grams=prin_paid,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            remarks=f"கடன் அசல் வரவு/முடிப்பு ({loan_row.get('loan_no')}) - ₹{prin_paid:,.0f}"
                        )

                    update_fields = {
                        "outstanding_principal": new_prin,
                        "last_interest_paid_date": txn_date
                    }
                    if action_type == "FULL_CLOSURE" or new_prin <= 0:
                        update_fields["status"] = "CLOSED"
                        update_fields["closed_date"] = txn_date
                        try:
                            supabase.table("test_gold_packets").update({
                                "is_loan_closed": True,
                                "updated_at": datetime.now(IST).isoformat()
                            }).eq("loan_no", loan_row["loan_no"]).execute()
                        except Exception as pe:
                            print("Packet close flag update note:", pe)

                    supabase.table("test_gold_loans").update(update_fields).eq("id", loan_id).execute()

            elif item.get("is_gold_purchase") is True:
                gp_meta = item.get("gp_meta") or {}
                gp_items = gp_meta.get("items") or []
                if gp_items:
                    br_res = supabase.table("test_branches").select("branch_code").eq("id", data.branch_id).execute()
                    b_code = br_res.data[0]["branch_code"].strip().upper() if br_res.data else "BR"
                    cnt_res = supabase.table("test_gold_purchases").select("id", count="exact").eq("branch_id", data.branch_id).execute()
                    next_seq = (cnt_res.count or len(cnt_res.data or [])) + 1
                    final_gp_no = f"{b_code}/GP/{next_seq:04d}"

                    tot_gross = sum(float(x.get("gross_weight") or 0) for x in gp_items)
                    tot_net = sum(float(x.get("net_weight") or 0) for x in gp_items)
                    tot_amt = sum(float(x.get("item_amount") or 0) for x in gp_items)

                    gp_master = {
                        "gp_no": final_gp_no,
                        "branch_id": data.branch_id,
                        "customer_id": data.customer_id,
                        "visit_id": target_visit_id,
                        "transaction_date": txn_date,
                        "total_items": len(gp_items),
                        "total_gross_weight": round(tot_gross, 3),
                        "total_net_weight": round(tot_net, 3),
                        "total_purchase_amount": round(tot_amt, 2),
                        "handover_photo_url": gp_meta.get("handover_photo"),
                        "status": "COMPLETED"
                    }
                    gp_ins = supabase.table("test_gold_purchases").insert(gp_master).execute()
                    if gp_ins.data:
                        new_gp_id = gp_ins.data[0]["id"]
                        total_cnt = len(gp_items)
                        items_to_save = []
                        for idx, g_item in enumerate(gp_items, start=1):
                            tag_no = f"{final_gp_no}/{idx}/{total_cnt}"
                            items_to_save.append({
                                "purchase_id": new_gp_id,
                                "item_tag_no": tag_no,
                                "item_type": g_item.get("item_type"),
                                "quantity": int(g_item.get("quantity") or 1),
                                "gross_weight": float(g_item.get("gross_weight") or 0),
                                "net_weight": float(g_item.get("net_weight") or 0),
                                "purity": g_item.get("purity"),
                                "rate_per_gram": float(g_item.get("rate_per_gram") or 0),
                                "item_amount": float(g_item.get("item_amount") or 0),
                                "item_photo_url": g_item.get("item_photo"),
                                "stock_status": "AT_BRANCH"
                            })
                        supabase.table("test_gold_purchase_items").insert(items_to_save).execute()

                    # 🏆 பழைய தங்கம் வாங்குதல் இன்சென்டிவ் புள்ளிகள் (கிராம் கணக்கில்)
                    if tot_net > 0:
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="OLD_GOLD",
                            ref_no=final_gp_no,
                            amount_or_grams=tot_net,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            remarks=f"பழைய தங்கம் கொள்முதல் ({final_gp_no}) - {tot_net:.3f}g"
                        )

            elif item.get("is_gold_sale") is True:
                gs_meta = item.get("gs_meta") or {}
                stock_item_id = gs_meta.get("stock_item_id")
                if stock_item_id:
                    br_res = supabase.table("test_branches").select("branch_code").eq("id", data.branch_id).execute()
                    b_code = br_res.data[0]["branch_code"].strip().upper() if br_res.data else "BR"
                    cnt_res = supabase.table("test_gold_sales").select("id", count="exact").eq("branch_id", data.branch_id).execute()
                    next_gs_seq = (cnt_res.count or len(cnt_res.data or [])) + 1
                    final_gs_no = f"{b_code}/GS/{next_gs_seq:04d}"
                    sale_net_wt = float(gs_meta.get("net_weight") or 0)

                    gs_record = {
                        "gs_no": final_gs_no,
                        "branch_id": data.branch_id,
                        "customer_id": data.customer_id,
                        "visit_id": target_visit_id,
                        "purchase_item_id": stock_item_id,
                        "item_tag_no": gs_meta.get("item_tag_no", "-"),
                        "transaction_date": txn_date,
                        "net_weight": sale_net_wt,
                        "gold_value": float(gs_meta.get("gold_value") or 0),
                        "making_charge": float(gs_meta.get("making_charge") or 0),
                        "gst_amount": float(gs_meta.get("gst_amount") or 0),
                        "total_sale_amount": float(gs_meta.get("total_sale_amount") or 0)
                    }
                    supabase.table("test_gold_sales").insert(gs_record).execute()
                    supabase.table("test_gold_purchase_items").update({"stock_status": "SOLD"}).eq("id", stock_item_id).execute()

                    # 🏆 நகை விற்பனை இன்சென்டிவ் புள்ளிகள் (கிராம் கணக்கில்)
                    if sale_net_wt > 0:
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="GOLD_SALE",
                            ref_no=final_gs_no,
                            amount_or_grams=sale_net_wt,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            remarks=f"நகை விற்பனை ({final_gs_no}) - {sale_net_wt:.3f}g"
                        )

            elif item.get("is_gss_account") is True:
                gss_meta = item.get("gss_meta") or {}
                mode = gss_meta.get("mode", "NEW")
                gss_no = gss_meta.get("gss_no")
                scheme_id = int(gss_meta.get("scheme_id") or 1)
                init_amount = float(gss_meta.get("initial_amount") or 0)
                penalty_amt = float(gss_meta.get("penalty_amount") or 0)
                gold_rate = float(gss_meta.get("gold_rate") or 0)
                wt_credited = float(gss_meta.get("weight_credited") or 0)
                maturity_opt = gss_meta.get("maturity_option", "GOLD")

                if mode == "CLOSE":
                    acc_id = gss_meta.get("account_id")
                    if acc_id:
                        supabase.table("test_customer_savings_accounts").update({
                            "status": "CLOSED",
                            "maturity_option": gss_meta.get("close_type", "GOLD")
                        }).eq("id", acc_id).execute()
                else:
                    acc_res = supabase.table("test_customer_savings_accounts").select("*").eq("gss_no", gss_no).execute()
                    if acc_res.data:
                        acc_row = acc_res.data[0]
                        account_id = acc_row["id"]
                        old_total = float(acc_row.get("total_amount_paid") or 0)
                        old_wt = float(acc_row.get("total_accumulated_weight") or 0)
                        old_penalty = float(acc_row.get("total_penalty_accrued") or 0)

                        supabase.table("test_savings_transactions").insert({
                            "account_id": account_id,
                            "visit_id": target_visit_id,
                            "transaction_date": txn_date,
                            "amount_paid": init_amount,
                            "gold_rate_on_day": gold_rate,
                            "weight_credited": wt_credited,
                            "penalty_amount": penalty_amt,
                            "receipt_no": f"{gss_no}/INST"
                        }).execute()

                        supabase.table("test_customer_savings_accounts").update({
                            "total_amount_paid": round(old_total + init_amount, 2),
                            "total_accumulated_weight": round(old_wt + wt_credited, 3),
                            "total_penalty_accrued": round(old_penalty + penalty_amt, 2)
                        }).eq("id", account_id).execute()

                        # 🏆 GSS தவணை வசூல் இன்சென்டிவ் புள்ளிகள்
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="GSS_INST",
                            ref_no=gss_no,
                            amount_or_grams=init_amount,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            remarks=f"GSS தவணை வசூல் ({gss_no})"
                        )
                    else:
                        new_acc_res = supabase.table("test_customer_savings_accounts").insert({
                            "gss_no": gss_no,
                            "customer_id": data.customer_id,
                            "branch_id": data.branch_id,
                            "scheme_id": scheme_id,
                            "start_date": txn_date,
                            "maturity_option": maturity_opt,
                            "total_amount_paid": round(init_amount, 2),
                            "total_accumulated_weight": round(wt_credited, 3),
                            "total_penalty_accrued": round(penalty_amt, 2),
                            "status": "ACTIVE"
                        }).execute()

                        if new_acc_res.data:
                            new_account_id = new_acc_res.data[0]["id"]
                            supabase.table("test_savings_transactions").insert({
                                "account_id": new_account_id,
                                "visit_id": target_visit_id,
                                "transaction_date": txn_date,
                                "amount_paid": init_amount,
                                "gold_rate_on_day": gold_rate,
                                "weight_credited": wt_credited,
                                "penalty_amount": penalty_amt,
                                "receipt_no": f"{gss_no}/NEW"
                            }).execute()

                        # 🏆 GSS புதிய சேர்க்கை இன்சென்டிவ் புள்ளிகள்
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="GSS_JOIN",
                            ref_no=gss_no,
                            amount_or_grams=init_amount,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            remarks=f"புதிய GSS திட்டம் துவக்கம் ({gss_no})"
                        )

            elif item.get("is_rd_account") is True:
                rd_meta = item.get("rd_meta") or {}
                mode = rd_meta.get("mode", "NEW")
                rd_no = rd_meta.get("rd_no")
                scheme_id = int(rd_meta.get("scheme_id") or 1)
                init_amount = float(rd_meta.get("initial_amount") or 0)

                if mode == "CLOSE":
                    acc_id = rd_meta.get("account_id")
                    if acc_id:
                        supabase.table("test_customer_rd_accounts").update({"status": "CLOSED"}).eq("id", acc_id).execute()
                else:
                    acc_res = supabase.table("test_customer_rd_accounts").select("*").eq("rd_no", rd_no).execute()
                    if acc_res.data:
                        acc_row = acc_res.data[0]
                        account_id = acc_row["id"]
                        old_total = float(acc_row.get("total_amount_paid") or 0)
                        supabase.table("test_rd_transactions").insert({
                            "account_id": account_id,
                            "visit_id": target_visit_id,
                            "transaction_date": txn_date,
                            "amount_paid": init_amount,
                            "receipt_no": f"{rd_no}/INST"
                        }).execute()
                        supabase.table("test_customer_rd_accounts").update({
                            "total_amount_paid": round(old_total + init_amount, 2)
                        }).eq("id", account_id).execute()

                        # 🏆 RD தவணை வசூல் இன்சென்டிவ் புள்ளிகள்
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="RD_INST",
                            ref_no=rd_no,
                            amount_or_grams=init_amount,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            scheme_id=scheme_id,
                            remarks=f"RD தவணை வசூல் ({rd_no})"
                        )
                    else:
                        new_acc = supabase.table("test_customer_rd_accounts").insert({
                            "rd_no": rd_no,
                            "customer_id": data.customer_id,
                            "branch_id": data.branch_id,
                            "scheme_id": scheme_id,
                            "start_date": txn_date,
                            "total_amount_paid": round(init_amount, 2),
                            "nominee_name": rd_meta.get("nominee_name"),
                            "nominee_relation": rd_meta.get("nominee_relation"),
                            "nominee_mobile": rd_meta.get("nominee_mobile"),
                            "status": "ACTIVE"
                        }).execute()
                        if new_acc.data:
                            new_acc_id = new_acc.data[0]["id"]
                            supabase.table("test_rd_transactions").insert({
                                "account_id": new_acc_id,
                                "visit_id": target_visit_id,
                                "transaction_date": txn_date,
                                "amount_paid": init_amount,
                                "receipt_no": f"{rd_no}/NEW"
                            }).execute()

                        # 🏆 RD புதிய சேர்க்கை இன்சென்டிவ் புள்ளிகள்
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="RD_JOIN",
                            ref_no=rd_no,
                            amount_or_grams=init_amount,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            scheme_id=scheme_id,
                            remarks=f"புதிய RD திட்டம் துவக்கம் ({rd_no})"
                        )

            elif item.get("is_si_account") and item.get("si_meta"):
                sm = item["si_meta"]
                s_mode = sm.get("mode")
                if s_mode == "NEW":
                    prin_val = float(sm.get("principal_amount") or 0)
                    si_no_val = sm.get("si_no")
                    supabase.table("test_si_accounts").insert({
                        "si_no": si_no_val,
                        "customer_id": data.customer_id,
                        "branch_id": data.branch_id,
                        "scheme_id": sm.get("scheme_id"),
                        "principal_amount": prin_val,
                        "nominees": sm.get("nominees", []),
                        "status": "ACTIVE"
                    }).execute()

                    # 🏆 FD / SI புதிய வைப்பு இன்சென்டிவ் புள்ளிகள்
                    if prin_val > 0:
                        record_incentive_points(
                            branch_id=data.branch_id,
                            txn_type="FD_NEW",
                            ref_no=si_no_val,
                            amount_or_grams=prin_val,
                            source_staff_id=item_src_staff,
                            txn_date=txn_date,
                            remarks=f"புதிய FD / SI வைப்பு ({si_no_val}) - ₹{prin_val:,.0f}"
                        )
                elif s_mode == "RETURN_PAYOUT":
                    acc_id = sm.get("account_id")
                    ret_amt = float(sm.get("return_amount", 0))
                    supabase.table("test_si_return_payouts").insert({
                        "si_account_id": acc_id,
                        "visit_id": target_visit_id,
                        "settlement_id": new_settle_id,
                        "voucher_no": f"SIV-{new_settle_id}-{acc_id}",
                        "payout_date": txn_date,
                        "period_label": sm.get("period_label", "Periodic Return"),
                        "return_amount": ret_amt
                    }).execute()
                    cur = supabase.table("test_si_accounts").select("total_return_paid").eq("id", acc_id).execute()
                    prev_paid = float(cur.data[0]["total_return_paid"] or 0) if cur.data else 0
                    supabase.table("test_si_accounts").update({"total_return_paid": prev_paid + ret_amt}).eq("id", acc_id).execute()
                elif s_mode == "CLOSE":
                    acc_id = sm.get("account_id")
                    supabase.table("test_si_accounts").update({
                        "status": "CLOSED",
                        "closed_at": datetime.now(IST).isoformat()
                    }).eq("id", acc_id).execute()

        return {"status": "success", "message": "பரிவர்த்தனை முடிந்தது!", "settlement_id": new_settle_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தீர்வுப் பிழை: {str(e)}")

# =========================================================================
# 🔐 நகைக்கடன் பாக்கெட் & லாக்கர் மேலாண்மை (Gold Packet Lifecycle APIs)
# =========================================================================

@app.get("/api/packets/list")
def get_gold_packets(branch_id: Optional[int] = None, role: str = "BRANCH"):
    try:
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        c_map = {c["id"]: c for c in (cust_res.data or [])}

        br_res = supabase.table("test_branches").select("id, branch_name, branch_code").execute()
        b_map = {b["id"]: b for b in (br_res.data or [])}

        # ரத்து செய்யப்பட்ட (CANCELLED) கடன்களின் எண்களைப் பெற்று, ரத்து செய்யப்பட்ட பாக்கெட்டுகளை மறைத்தல்
        cancelled_loan_nos = set()
        try:
            c_loans = supabase.table("test_gold_loans").select("loan_no, status").eq("status", "CANCELLED").execute().data or []
            for cl in c_loans:
                if cl.get("loan_no"):
                    cancelled_loan_nos.add(str(cl["loan_no"]).strip().upper())
        except Exception:
            pass

        query = supabase.table("test_gold_packets").select("*").neq("packet_status", "CANCELLED")
        if role != "HQ" and branch_id:
            query = query.eq("branch_id", branch_id)
        res = query.order("updated_at", desc=True).execute()

        packets = []
        for p in (res.data or []):
            lno_clean = str(p.get("loan_no") or "").strip().upper()
            if lno_clean in cancelled_loan_nos:
                continue
            p["test_customers"] = c_map.get(p.get("customer_id"), {"name": "-", "mobile": "-"})
            p["test_branches"] = b_map.get(p.get("branch_id"), {"branch_name": "-", "branch_code": "BR"})
            packets.append(p)

        return {"status": "success", "data": packets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/packets/dispatch-to-hq")
def dispatch_packets_to_hq(data: dict):
    try:
        loan_nos = data.get("loan_nos") or []
        carrier = str(data.get("carrier_person") or "").strip()
        staff_id = data.get("staff_id") or 1
        if not loan_nos or not carrier:
            raise HTTPException(status_code=400, detail="பாக்கெட்டுகள் மற்றும் கொண்டு செல்பவர் பெயர் அவசியம்.")

        now_t = datetime.now(IST).isoformat()
        sent_count = 0
        for lno in loan_nos:
            pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
            if not pkt_res.data:
                continue
            pkt = pkt_res.data[0]
            if pkt.get("is_handed_over") or pkt.get("packet_status") != "AT_BRANCH_NEW":
                continue

            supabase.table("test_gold_packets").update({
                "packet_status": "IN_TRANSIT_TO_HQ",
                "current_location": "TRANSIT",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()

            supabase.table("test_gold_packet_movements").insert({
                "packet_id": pkt["id"],
                "loan_no": lno,
                "action_type": "DISPATCH_TO_HQ",
                "from_location": "BRANCH",
                "to_location": "HQ_VAULT",
                "carrier_person": carrier,
                "performed_by": staff_id,
                "remarks": f"கிளையிலிருந்து HQ-க்கு அனுப்பப்பட்டது (கொண்டு செல்பவர்: {carrier})"
            }).execute()
            sent_count += 1

        if sent_count == 0:
            raise HTTPException(status_code=400, detail="தேர்வு செய்த பாக்கெட்டுகள் அனுப்பும் நிலையில் இல்லை!")
        return {"status": "success", "message": f"{sent_count} பாக்கெட்டுகள் தலைமையகத்திற்கு அனுப்பப்பட்டன!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/packets/receive-vault")
def receive_packets_hq_vault(data: dict):
    try:
        loan_nos = data.get("loan_nos") or []
        staff_id = data.get("staff_id") or 1
        now_t = datetime.now(IST).isoformat()
        for lno in loan_nos:
            pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
            if not pkt_res.data:
                continue
            pkt = pkt_res.data[0]
            supabase.table("test_gold_packets").update({
                "packet_status": "AT_HQ_VAULT",
                "current_location": "HQ_VAULT",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()

            supabase.table("test_gold_packet_movements").insert({
                "packet_id": pkt["id"],
                "loan_no": lno,
                "action_type": "HQ_VAULT_VERIFIED",
                "from_location": "TRANSIT",
                "to_location": "HQ_VAULT",
                "verified_by_hq": True,
                "performed_by": staff_id,
                "remarks": "தலைமையக லாக்கரில் பாக்கெட் வாரியாகச் சரிபார்க்கப்பட்டு வைக்கப்பட்டது"
            }).execute()
        return {"status": "success", "message": f"{len(loan_nos)} பாக்கெட்டுகள் சரிபார்க்கப்பட்டு HQ லாக்கரில் வைக்கப்பட்டன."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/packets/bank-pledge")
def pledge_packets_in_bank(data: dict):
    try:
        loan_nos = data.get("loan_nos") or []
        comp_bank_id = int(data.get("company_bank_id") or 0)
        bank_loan_ref = str(data.get("bank_loan_ref") or "-").strip()
        total_received = float(data.get("total_received_amount") or 0)
        bank_charges = float(data.get("bank_charges") or 0)
        token_photo = data.get("token_photo")
        staff_id = int(data.get("staff_id") or 1)

        if not loan_nos or not comp_bank_id or total_received <= 0:
            raise HTTPException(status_code=400, detail="நிறுவன வங்கி, தொகை மற்றும் பாக்கெட்டுகளைச் சரியாக உள்ளிடவும்.")
        if not token_photo:
            raise HTTPException(status_code=400, detail="📸 வங்கி அளித்த டோக்கன் படத்தைக் கட்டாயம் பதிவேற்றவும்!")

        bk_res = supabase.table("test_company_banks").select("bank_name, account_no").eq("id", comp_bank_id).execute()
        bank_name = f"{bk_res.data[0]['bank_name']} ({bk_res.data[0]['account_no']})" if bk_res.data else "Company Bank"

        valid_packets = []
        for lno in loan_nos:
            pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
            if not pkt_res.data:
                continue
            pkt = pkt_res.data[0]
            if pkt.get("current_location") != "HQ_VAULT" or pkt.get("packet_status") != "AT_HQ_VAULT":
                raise HTTPException(
                    status_code=400,
                    detail=f"❌ பாக்கெட் ({lno}) தலைமையக லாக்கரில் (HQ_VAULT) இல்லை! HQ லாக்கரில் உள்ள பாக்கெட்டுகளை மட்டுமே வங்கி லாக்கரில் வைக்க முடியும்."
                )
            valid_packets.append(pkt)

        now_t = datetime.now(IST).isoformat()
        for pkt in valid_packets:
            supabase.table("test_gold_packets").update({
                "bank_verify_status": "PENDING_PLEDGE_VERIFY",
                "bank_initiated_by": staff_id,
                "bank_token_photo": token_photo,
                "pending_request_type": "BANK_PLEDGE_VERIFY",
                "pending_request_status": "PENDING",
                "pending_request_data": {
                    "bank_name": bank_name,
                    "bank_loan_ref": bank_loan_ref,
                    "total_received": total_received,
                    "bank_charges": bank_charges,
                    "company_bank_id": comp_bank_id,
                    "packet_count": len(valid_packets)
                },
                "audit_notes": f"வங்கி லாக்கர் வைப்பு பதிவு ({bank_name}) - 2-வது HQ சரிபார்ப்பு நிலுவை",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()

        return {"status": "success", "message": f"{len(valid_packets)} பாக்கெட்டுகள் டோக்கனுடன் வங்கி லாக்கரில் வைக்கப் பதியப்பட்டன! மற்றொரு HQ பணியாளர் சரிபார்த்த பின் உறுதி செய்யப்படும்."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/packets/bank-redeem")
def redeem_packets_from_bank(data: dict):
    try:
        loan_nos = data.get("loan_nos") or []
        prin_paid = float(data.get("principal_paid") or 0)
        int_paid = float(data.get("interest_paid") or 0)
        comp_bank_id = int(data.get("company_bank_id") or 1)
        receipt_photo = data.get("receipt_photo")
        staff_id = int(data.get("staff_id") or 1)

        if not loan_nos:
            raise HTTPException(status_code=400, detail="மீட்க வேண்டிய பாக்கெட்டுகளைத் தேர்வு செய்யவும்.")
        if not receipt_photo:
            raise HTTPException(status_code=400, detail="📄 வங்கியிடம் பெற்ற ரசீதுப் படத்தைக் கட்டாயம் பதிவேற்றவும்!")

        valid_packets = []
        for lno in loan_nos:
            pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
            if not pkt_res.data:
                continue
            pkt = pkt_res.data[0]
            if pkt.get("current_location") != "BANK_LOCKER" or pkt.get("packet_status") != "PLEDGED_IN_BANK":
                raise HTTPException(
                    status_code=400,
                    detail=f"❌ பாக்கெட் ({lno}) வங்கி லாக்கரில் இல்லை! வங்கி லாக்கரில் உள்ள பாக்கெட்டுகளை மட்டுமே மீட்க முடியும்."
                )
            valid_packets.append(pkt)

        now_t = datetime.now(IST).isoformat()
        for pkt in valid_packets:
            supabase.table("test_gold_packets").update({
                "bank_verify_status": "PENDING_REDEEM_VERIFY",
                "bank_initiated_by": staff_id,
                "bank_redeem_receipt_photo": receipt_photo,
                "pending_request_type": "BANK_REDEEM_VERIFY",
                "pending_request_status": "PENDING",
                "pending_request_data": {
                    "principal_paid": prin_paid,
                    "interest_paid": int_paid,
                    "company_bank_id": comp_bank_id,
                    "packet_count": len(valid_packets)
                },
                "audit_notes": "வங்கியிலிருந்து மீட்பு பதிவு செய்யப்பட்டது - 2-வது HQ சரிபார்ப்பு நிலுவை",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()

        return {"status": "success", "message": f"{len(valid_packets)} பாக்கெட்டுகள் ரசீதுடன் மீட்கப் பதியப்பட்டன! மற்றொரு HQ பணியாளர் சரிபார்த்த பின் உறுதி செய்யப்படும்."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/packets/action")
def hq_packet_action(data: dict):
    try:
        lno = str(data.get("loan_no") or "").strip()
        act_type = str(data.get("action_type") or "").strip()
        carrier = str(data.get("carrier_person") or "").strip()
        admin_id = data.get("admin_id") or 1

        pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
        if not pkt_res.data:
            raise HTTPException(status_code=404, detail="பாக்கெட் இல்லை")
        pkt = pkt_res.data[0]
        now_t = datetime.now(IST).isoformat()

        if act_type == "SEND_TO_BRANCH":
            if pkt.get("current_location") == "BANK_LOCKER":
                raise HTTPException(status_code=400, detail="இந்தப் பாக்கெட் வங்கி லாக்கரில் உள்ளது! முதலில் வங்கியிலிருந்து மீட்டு HQ கொண்டு வந்த பின்னரே கிளைக்கு அனுப்ப முடியும்.")
            if pkt.get("packet_status") != "REQUESTED_BY_BRANCH":
                raise HTTPException(status_code=400, detail=f"❌ பாக்கெட் ({lno})-க்கு கிளையிலிருந்து கோரிக்கை வரவில்லை! கிளை கோரிக்கை வைத்த பாக்கெட்டுகளை மட்டுமே அனுப்ப முடியும்.")

            supabase.table("test_gold_packets").update({
                "packet_status": "IN_TRANSIT_TO_BRANCH",
                "current_location": "TRANSIT",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()
            supabase.table("test_gold_packet_movements").insert({
                "packet_id": pkt["id"],
                "loan_no": lno,
                "action_type": "DISPATCH_TO_BRANCH",
                "from_location": "HQ_VAULT",
                "to_location": "BRANCH",
                "carrier_person": carrier,
                "performed_by": admin_id,
                "remarks": f"கிளை கோரிக்கையின் பேரில் தலைமையகத்திலிருந்து அனுப்பப்பட்டது (கொண்டு செல்பவர்: {carrier})"
            }).execute()
            return {"status": "success", "message": f"பாக்கெட் ({lno}) கிளைக்கு அனுப்பப்பட்டது."}

        staff_chk = supabase.table("test_staff_users").select("can_approve_hq_packets").eq("id", admin_id).execute()
        if not staff_chk.data or not staff_chk.data[0].get("can_approve_hq_packets"):
            raise HTTPException(status_code=403, detail="❌ பாதுகாப்பு மறுப்பு: இந்த ஒப்புதலை வழங்க உங்களுக்கு நிர்வாக அனுமதி வழங்கப்படவில்லை!")

        if act_type == "APPROVE_SPECIAL":
            r_type = pkt.get("pending_request_type")
            r_data = pkt.get("pending_request_data") or {}
            if r_type == "DIRECT_RELEASE":
                supabase.table("test_gold_packets").update({
                    "packet_status": "AT_BRANCH_FOR_RELEASE",
                    "pending_request_status": "APPROVED",
                    "audit_notes": "HQ அனுமதியுடன் கிளையிலேயே நேரடியாக விடுவிக்க அனுமதிக்கப்பட்டது",
                    "updated_at": now_t
                }).eq("id", pkt["id"]).execute()
            elif r_type == "RETURN_UNCLAIMED":
                supabase.table("test_gold_packets").update({
                    "packet_status": "IN_TRANSIT_TO_HQ",
                    "current_location": "TRANSIT",
                    "pending_request_status": "APPROVED",
                    "audit_notes": "வாடிக்கையாளர் வராததால் HQ ஒப்புதலுடன் திரும்ப அனுப்பப்பட்டது",
                    "updated_at": now_t
                }).eq("id", pkt["id"]).execute()
            elif r_type == "REPLEDGE_TRANSFER":
                new_lno = str(r_data.get("new_loan_no") or "").strip()
                old_lno = pkt["loan_no"]

                dup_res = supabase.table("test_gold_packets").select("id, current_location").eq("loan_no", new_lno).execute()
                for d in (dup_res.data or []):
                    if d["id"] != pkt["id"]:
                        supabase.table("test_gold_packet_movements").delete().eq("packet_id", d["id"]).execute()
                        supabase.table("test_gold_packets").delete().eq("id", d["id"]).execute()

                note = f"பழைய கடன் ({old_lno}) முடித்து, புதிய கடன் ({new_lno})-க்கு மறு-அடகு மாற்றப்பட்டது."
                supabase.table("test_gold_packets").update({
                    "loan_no": new_lno,
                    "previous_loan_no": old_lno,
                    "is_loan_closed": False,
                    "is_handed_over": False,
                    "pending_request_status": "APPROVED",
                    "audit_notes": note,
                    "updated_at": now_t
                }).eq("id", pkt["id"]).execute()
                supabase.table("test_gold_packet_movements").insert({
                    "packet_id": pkt["id"],
                    "loan_no": new_lno,
                    "action_type": "REPLEDGE_NUMBER_CHANGED",
                    "from_location": pkt["current_location"],
                    "to_location": pkt["current_location"],
                    "verified_by_hq": True,
                    "performed_by": admin_id,
                    "remarks": note
                }).execute()
            return {"status": "success", "message": "சிறப்பு ஒப்புதல் வெற்றிகரமாக வழங்கப்பட்டது!"}

        supabase.table("test_gold_packets").update({"pending_request_status": "REJECTED", "updated_at": now_t}).eq("id", pkt["id"]).execute()
        return {"status": "success", "message": "கோரிக்கை நிராகரிக்கப்பட்டது."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/packets/verify-bank-action")
def verify_bank_locker_second_staff(data: dict):
    try:
        lno = str(data.get("loan_no") or "").strip()
        verifier_id = int(data.get("verifier_id") or 1)
        action = str(data.get("action") or "APPROVE")

        pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
        if not pkt_res.data:
            raise HTTPException(status_code=404, detail="பாக்கெட் இல்லை")
        pkt = pkt_res.data[0]

        if pkt.get("bank_initiated_by") and int(pkt.get("bank_initiated_by")) == verifier_id:
            raise HTTPException(status_code=400, detail="❌ பாதுகாப்பு விதி: இந்தப் பதிவைச் செய்த அதே பணியாளர் சரிபார்க்க முடியாது! மற்றொரு தலைமையகப் பணியாளர் சரிபார்க்க வேண்டும்.")

        now_t = datetime.now(IST).isoformat()
        v_status = pkt.get("bank_verify_status")
        r_data = pkt.get("pending_request_data") or {}

        if action == "REJECT":
            supabase.table("test_gold_packets").update({
                "bank_verify_status": "NONE",
                "pending_request_status": "REJECTED",
                "audit_notes": "2-வது HQ பணியாளரால் வங்கி நடவடிக்கை நிராகரிக்கப்பட்டது",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()
            return {"status": "success", "message": "வங்கி நடவடிக்கை நிராகரிக்கப்பட்டது."}

        comp_bank_id = int(r_data.get("company_bank_id") or 1)
        cnt = max(1, int(r_data.get("packet_count") or 1))

        if v_status == "PENDING_PLEDGE_VERIFY":
            bank_name = r_data.get("bank_name", "-")
            bank_ref = r_data.get("bank_loan_ref", "-")
            share_amt = float(r_data.get("total_received") or 0) / cnt
            share_chg = float(r_data.get("bank_charges") or 0) / cnt
            net_credit = share_amt - share_chg

            supabase.table("test_gold_packets").update({
                "packet_status": "PLEDGED_IN_BANK",
                "current_location": "BANK_LOCKER",
                "bank_name": bank_name,
                "bank_loan_ref": bank_ref,
                "bank_pledge_amount": round(share_amt, 2),
                "bank_charges_amount": round(share_chg, 2),
                "bank_verify_status": "VERIFIED",
                "pending_request_status": "APPROVED",
                "audit_notes": f"2-வது HQ பணியாளரால் சரிபார்க்கப்பட்டு வங்கி லாக்கரில் வைக்கப்பட்டது ({bank_name})",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()

            supabase.table("test_gold_packet_movements").insert({
                "packet_id": pkt["id"], "loan_no": lno, "action_type": "BANK_LOCKER_PLEDGE_VERIFIED",
                "from_location": "HQ_VAULT", "to_location": "BANK_LOCKER",
                "company_bank_id": comp_bank_id, "amount_involved": round(share_amt, 2),
                "charges_or_interest": round(share_chg, 2), "verified_by_hq": True,
                "performed_by": verifier_id, "remarks": f"2-வது HQ சரிபார்ப்பு முடிந்து வங்கியில் வைக்கப்பட்டது ({bank_name})"
            }).execute()

            bk_res = supabase.table("test_company_banks").select("*").eq("id", comp_bank_id).execute()
            if bk_res.data:
                for bal_col in ["current_balance", "balance", "opening_balance"]:
                    if bal_col in bk_res.data[0]:
                        old_bal = float(bk_res.data[0].get(bal_col) or 0)
                        supabase.table("test_company_banks").update({bal_col: old_bal + net_credit}).eq("id", comp_bank_id).execute()
                        break

        elif v_status == "PENDING_REDEEM_VERIFY":
            share_prin = float(r_data.get("principal_paid") or 0) / cnt
            share_int = float(r_data.get("interest_paid") or 0) / cnt
            total_debit = share_prin + share_int

            supabase.table("test_gold_packets").update({
                "packet_status": "AT_HQ_VAULT",
                "current_location": "HQ_VAULT",
                "bank_verify_status": "VERIFIED",
                "pending_request_status": "APPROVED",
                "audit_notes": "2-வது HQ பணியாளரால் சரிபார்க்கப்பட்டு வங்கியிலிருந்து மீட்கப்பட்டது",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()

            supabase.table("test_gold_packet_movements").insert({
                "packet_id": pkt["id"], "loan_no": lno, "action_type": "BANK_LOCKER_REDEEM_VERIFIED",
                "from_location": "BANK_LOCKER", "to_location": "HQ_VAULT",
                "company_bank_id": comp_bank_id, "amount_involved": round(share_prin, 2),
                "charges_or_interest": round(share_int, 2), "verified_by_hq": True,
                "performed_by": verifier_id, "remarks": "2-வது HQ சரிபார்ப்பு முடிந்து வங்கியிலிருந்து மீட்கப்பட்டது"
            }).execute()

            bk_res = supabase.table("test_company_banks").select("*").eq("id", comp_bank_id).execute()
            if bk_res.data:
                for bal_col in ["current_balance", "balance", "opening_balance"]:
                    if bal_col in bk_res.data[0]:
                        old_bal = float(bk_res.data[0].get(bal_col) or 0)
                        supabase.table("test_company_banks").update({bal_col: old_bal - total_debit}).eq("id", comp_bank_id).execute()
                        break

        return {"status": "success", "message": f"✅ பாக்கெட் ({lno}) 2-வது HQ பணியாளரால் சரிபார்க்கப்பட்டு உறுதி செய்யப்பட்டது!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/packets/special-request")
def create_packet_special_request(data: dict):
    try:
        lno = str(data.get("loan_no") or "").strip()
        req_type = str(data.get("request_type") or "").strip()
        new_lno = str(data.get("new_loan_no") or "").strip()
        remarks = str(data.get("remarks") or "").strip()

        pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
        if not pkt_res.data:
            raise HTTPException(status_code=404, detail="பாக்கெட் விபரம் கிடைக்கவில்லை")
        pkt = pkt_res.data[0]
        now_t = datetime.now(IST).isoformat()

        if req_type in ["DIRECT_RELEASE", "REPLEDGE_TRANSFER"] and not pkt.get("is_loan_closed"):
            raise HTTPException(status_code=400, detail="❌ முதலில் கவுண்ட்டரில் நகைக்கடனை முழுமையாக முடித்த பின்னரே இந்தக் கோரிக்கையை அனுப்ப முடியும்!")

        if req_type == "REQUEST_FROM_HQ":
            supabase.table("test_gold_packets").update({
                "packet_status": "REQUESTED_BY_BRANCH",
                "audit_notes": remarks or "கிளையிலிருந்து பாக்கெட் கோரப்பட்டுள்ளது",
                "updated_at": now_t
            }).eq("id", pkt["id"]).execute()
            return {"status": "success", "message": "பாக்கெட் கேட்டு தலைமையகத்திற்கு வேண்டுகோள் அனுப்பப்பட்டது."}

        supabase.table("test_gold_packets").update({
            "pending_request_type": req_type,
            "pending_request_data": {"new_loan_no": new_lno, "remarks": remarks},
            "pending_request_status": "PENDING",
            "updated_at": now_t
        }).eq("id", pkt["id"]).execute()

        return {"status": "success", "message": "தலைமையக ஒப்புதலுக்குக் கோரிக்கை அனுப்பப்பட்டது."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/packets/branch-receive")
def branch_receive_packet(loan_no: str = Query(...), staff_id: int = Query(1)):
    try:
        pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", loan_no.strip()).execute()
        if not pkt_res.data:
            raise HTTPException(status_code=404, detail="பாக்கெட் இல்லை")
        pkt = pkt_res.data[0]
        supabase.table("test_gold_packets").update({
            "packet_status": "AT_BRANCH_FOR_RELEASE",
            "current_location": "BRANCH",
            "updated_at": datetime.now(IST).isoformat()
        }).eq("id", pkt["id"]).execute()
        return {"status": "success", "message": "பாக்கெட் கிளையில் பெறப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/packets/send-handover-otp")
def trigger_packet_handover_otp(loan_no: str = Query(...)):
    try:
        pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", loan_no.strip()).execute()
        if not pkt_res.data:
            raise HTTPException(status_code=404, detail="பாக்கெட் இல்லை")
        pkt = pkt_res.data[0]

        if not pkt.get("is_loan_closed"):
            raise HTTPException(status_code=400, detail="❌ இந்த நகைக்கடன் இன்னும் முடிக்கப்படவில்லை! முதலில் கவுண்ட்டரில் கடனை முடிக்கவும்.")

        if pkt.get("is_handed_over"):
            raise HTTPException(status_code=400, detail="❌ இந்தப் பாக்கெட் ஏற்கனவே வாடிக்கையாளரிடம் ஒப்படைக்கப்பட்டுவிட்டது!")

        if pkt.get("packet_status") == "AT_BRANCH_NEW" and pkt.get("pending_request_status") != "APPROVED":
            raise HTTPException(status_code=400, detail="❌ HQ செல்லாமல் கிளையிலேயே வைத்துத் திருப்ப தலைமையக ஒப்புதல் அவசியம்!")

        if pkt.get("current_location") != "BRANCH" or pkt.get("packet_status") != "AT_BRANCH_FOR_RELEASE":
            raise HTTPException(status_code=400, detail="❌ பாக்கெட் இன்னும் கிளையில் ஒப்படைப்புக்குத் தயாராக இல்லை!")

        cust_res = supabase.table("test_customers").select("name, mobile").eq("id", pkt["customer_id"]).execute()
        cust = cust_res.data[0] if cust_res.data else {}
        mobile = cust.get("mobile")
        if not mobile:
            raise HTTPException(status_code=400, detail="வாடிக்கையாளர் மொபைல் எண் இல்லை.")

        otp = str(random.randint(100000, 999999))
        supabase.table("test_gold_packets").update({"handover_otp": otp}).eq("id", pkt["id"]).execute()
        ok, msg = send_packet_handover_sms(mobile, otp, loan_no.strip())
        if not ok:
            raise HTTPException(status_code=502, detail=f"SMS பிழை: {msg}")
        return {"status": "success", "message": f"வாடிக்கையாளர் மொபைலுக்கு ({mobile}) OTP அனுப்பப்பட்டது!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/api/packets/verify-handover-otp")
def verify_packet_handover_otp(data: dict):
    try:
        lno = str(data.get("loan_no") or "").strip()
        otp_code = str(data.get("otp_code") or "").strip()
        is_exempted = bool(data.get("is_exempted", False))
        staff_id = data.get("staff_id") or 1

        pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
        if not pkt_res.data:
            raise HTTPException(status_code=404, detail="பாக்கெட் விபரம் கிடைக்கவில்லை.")
        pkt = pkt_res.data[0]

        if pkt.get("is_handed_over"):
            raise HTTPException(status_code=400, detail="இந்தப் பாக்கெட் ஏற்கனவே வாடிக்கையாளரிடம் ஒப்படைக்கப்பட்டுவிட்டது!")

        if is_exempted:
            if pkt.get("handover_otp_exempt_status") != "APPROVED":
                raise HTTPException(status_code=403, detail="❌ தலைமையகத்தின் OTP விலக்கு அனுமதி இன்னும் கிடைக்கவில்லை!")
            remark_txt = f"தலைமையக சிறப்பு அனுமதியுடன் OTP விலக்கு பெற்று ஒப்படைக்கப்பட்டது ({pkt.get('handover_otp_exempt_reason') or ''})"
        else:
            if str(pkt.get("handover_otp")) != otp_code:
                raise HTTPException(status_code=400, detail="தவறான OTP எண்! மீண்டும் சரிபார்க்கவும்.")
            remark_txt = "SMS OTP சரிபார்க்கப்பட்டு வாடிக்கையாளரிடம் பாக்கெட் ஒப்படைக்கப்பட்டது"

        now_t = datetime.now(IST).isoformat()
        supabase.table("test_gold_packets").update({
            "packet_status": "HANDED_OVER_TO_CUSTOMER",
            "current_location": "CUSTOMER",
            "is_handed_over": True,
            "handed_over_at": now_t,
            "audit_notes": remark_txt,
            "updated_at": now_t
        }).eq("id", pkt["id"]).execute()

        supabase.table("test_gold_packet_movements").insert({
            "packet_id": pkt["id"],
            "loan_no": lno,
            "action_type": "HANDED_OVER_OTP_EXEMPTED" if is_exempted else "HANDED_OVER_OTP_VERIFIED",
            "from_location": "BRANCH",
            "to_location": "CUSTOMER",
            "performed_by": staff_id,
            "remarks": remark_txt
        }).execute()
        return {"status": "success", "message": "🎉 நகை பாக்கெட் வாடிக்கையாளரிடம் வெற்றிகரமாக ஒப்படைக்கப்பட்டது!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================================================================
# 💰 தொடர்வைப்புத் திட்டம் (RD) API-கள்
# =========================================================================
@app.get("/api/rd/next-no")
def get_next_rd_no(branch_id: int):
    try:
        br_res = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        b_code = br_res.data[0]["branch_code"].strip().upper() if br_res.data else "BR"
        cnt_res = supabase.table("test_customer_rd_accounts").select("id", count="exact").eq("branch_id", branch_id).execute()
        seq = (cnt_res.count or len(cnt_res.data or [])) + 1
        return {"status": "success", "next_rd_no": f"{b_code}/RD/{seq:03d}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/rd-schemes")
def get_rd_schemes():
    try:
        res = supabase.table("test_rd_schemes").select("*").eq("is_active", True).order("id", desc=True).execute()
        return {"status": "success", "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/rd-scheme/{scheme_id}")
def delete_rd_scheme(scheme_id: int):
    try:
        supabase.table("test_rd_schemes").delete().eq("id", scheme_id).execute()
        return {"status": "success", "message": "RD திட்டம் நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/customer/{customer_id}/rd-accounts")
def get_customer_rd_accounts(customer_id: int):
    try:
        sch_res = supabase.table("test_rd_schemes").select("*").execute()
        sch_map = {s["id"]: s for s in (sch_res.data or [])}

        acc_res = supabase.table("test_customer_rd_accounts").select("*").eq("customer_id", customer_id).eq("status", "ACTIVE").execute()
        accounts = acc_res.data or []
        for acc in accounts:
            acc["scheme_details"] = sch_map.get(acc.get("scheme_id"), {})
            txn_res = supabase.table("test_rd_transactions").select("*").eq("account_id", acc["id"]).order("id", desc=False).execute()
            acc["transactions"] = txn_res.data or []

        return {"status": "success", "data": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/api/admin/rd-scheme/create")
def create_rd_scheme(data: dict):
    try:
        code = str(data.get("scheme_code") or "").strip().upper()
        min_amt = float(data.get("min_installment_amount") or data.get("monthly_amount") or 1000)
        tenure = int(data.get("tenure_count") or data.get("tenure_months") or 12)
        
        rec = {
            "scheme_code": code,
            "scheme_name": str(data.get("scheme_name") or "").strip(),
            "frequency": str(data.get("frequency") or "MONTHLY"),
            "min_installment_amount": min_amt,
            "monthly_amount": min_amt,
            "tenure_count": tenure,
            "tenure_months": tenure,
            "locking_period_count": int(data.get("locking_period_count") if data.get("locking_period_count") is not None else 3),
            "grace_period_days": int(data.get("grace_period_days") if data.get("grace_period_days") is not None else 5),
            "penalty_per_thousand": float(data.get("penalty_per_thousand") if data.get("penalty_per_thousand") is not None else 2),
            "interest_calculation_type": str(data.get("interest_calculation_type") or "COMPOUND"),
            "interest_rate": float(data.get("interest_rate") or 0),
            "maturity_per_thousand": float(data.get("maturity_per_thousand") or 0),
            "join_bonus_points": float(data.get("join_bonus_points") if data.get("join_bonus_points") is not None else 5.0),
            "per_1k_points": float(data.get("per_1k_points") if data.get("per_1k_points") is not None else 1.0),
            "is_active": True
        }
        res = supabase.table("test_rd_schemes").insert(rec).execute()
        return {"status": "success", "message": "புதிய தொடர்வைப்பு (RD) திட்டம் வெற்றிகரமாக உருவாக்கப்பட்டது!", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rd/request-maturity-benefit")
def request_rd_maturity_benefit(data: dict):
    try:
        acc_id = int(data.get("account_id"))
        proposed = float(data.get("proposed_benefit") or 0)
        supabase.table("test_customer_rd_accounts").update({
            "benefit_approval_status": "PENDING",
            "proposed_benefit_amount": proposed
        }).eq("id", acc_id).execute()
        return {"status": "success", "message": "RD மெச்சியுரிட்டி பெனிபிட் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hq/pending-rd-benefits")
def get_pending_rd_benefits():
    try:
        res = supabase.table("test_customer_rd_accounts").select("*, test_customers(name, mobile), test_branches(branch_name), test_rd_schemes(scheme_name)").eq("benefit_approval_status", "PENDING").execute()
        out = []
        for r in (res.data or []):
            out.append({
                "id": r["id"],
                "rd_no": r.get("rd_no"),
                "branch_name": (r.get("test_branches") or {}).get("branch_name", "-"),
                "customer_name": (r.get("test_customers") or {}).get("name", "-"),
                "customer_mobile": (r.get("test_customers") or {}).get("mobile", "-"),
                "scheme_name": (r.get("test_rd_schemes") or {}).get("scheme_name", "RD"),
                "total_amount_paid": r.get("total_amount_paid", 0),
                "total_penalty_accrued": r.get("total_penalty_accrued", 0),
                "proposed_benefit_amount": r.get("proposed_benefit_amount", 0)
            })
        return {"status": "success", "data": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-rd-benefit")
def approve_rd_benefit(data: dict):
    try:
        acc_id = int(data.get("account_id"))
        action = data.get("action")
        approved_amt = float(data.get("approved_amount") or 0)
        if action == "APPROVE":
            supabase.table("test_customer_rd_accounts").update({
                "benefit_approval_status": "APPROVED",
                "approved_benefit_amount": approved_amt
            }).eq("id", acc_id).execute()
            return {"status": "success", "message": f"₹{approved_amt} RD பெனிபிட் தொகைக்கு ஒப்புதல் அளிக்கப்பட்டது!"}
        else:
            supabase.table("test_customer_rd_accounts").update({
                "benefit_approval_status": "REJECTED",
                "approved_benefit_amount": 0
            }).eq("id", acc_id).execute()
            return {"status": "success", "message": "RD பெனிபிட் கோரிக்கை நிராகரிக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
# Schemes, Banks, Gold Rate, Branches, Staff
@app.get("/api/admin/schemes")
def get_loan_schemes():
    res = supabase.table("test_loan_schemes").select("*").eq("is_active", True).order("id", desc=True).execute()
    return {"status": "success", "data": res.data or []}

@app.post("/api/admin/scheme/create")
def create_loan_scheme(data: LoanSchemePayload):
    check = supabase.table("test_loan_schemes").select("id").eq("scheme_code", data.scheme_code.strip()).execute()
    if check.data:
        raise HTTPException(status_code=400, detail="திட்டக் குறியீடு ஏற்கனவே உள்ளது.")
    res = supabase.table("test_loan_schemes").insert(data.model_dump()).execute()
    return {"status": "success", "message": "புதிய நகைக்கடன் திட்டம் உருவாக்கப்பட்டது.", "data": res.data}

@app.delete("/api/admin/scheme/{scheme_id}")
def delete_loan_scheme(scheme_id: int):
    supabase.table("test_loan_schemes").delete().eq("id", scheme_id).execute()
    return {"status": "success", "message": "திட்டம் நீக்கப்பட்டது."}

@app.put("/api/admin/scheme/{scheme_id}")
def update_loan_scheme(scheme_id: int, data: LoanSchemePayload):
    check = supabase.table("test_loan_schemes").select("id").eq("scheme_code", data.scheme_code.strip()).neq("id", scheme_id).execute()
    if check.data:
        raise HTTPException(status_code=400, detail="இந்தத் திட்டக் குறியீடு ஏற்கனவே வேறொரு திட்டத்தில் உள்ளது.")
    res = supabase.table("test_loan_schemes").update(data.model_dump()).eq("id", scheme_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="திட்டம் கண்டறியப்படவில்லை.")
    return {"status": "success", "message": "திட்ட விவரங்கள் வெற்றிகரமாகப் புதுப்பிக்கப்பட்டன!", "data": res.data}

@app.patch("/api/admin/scheme/{scheme_id}/toggle-active")
def toggle_loan_scheme_active(scheme_id: int):
    curr = supabase.table("test_loan_schemes").select("is_active").eq("id", scheme_id).execute()
    if not curr.data:
        raise HTTPException(status_code=404, detail="திட்டம் கண்டறியப்படவில்லை.")
    current_status = curr.data[0].get("is_active")
    new_status = False if current_status is not False else True
    supabase.table("test_loan_schemes").update({"is_active": new_status}).eq("id", scheme_id).execute()
    status_text = "Active (செயலில்)" if new_status else "Deactive (நிறுத்தப்பட்டது)"
    return {"status": "success", "message": f"திட்டத்தின் நிலை '{status_text}' என மாற்றப்பட்டது!", "is_active": new_status}

@app.get("/api/admin/company-banks")
def get_company_banks():
    res = supabase.table("test_company_banks").select("*").eq("is_active", True).order("id", desc=True).execute()
    return {"status": "success", "data": res.data or []}

@app.post("/api/admin/company-bank/create")
def create_company_bank(data: CompanyBankPayload):
    res = supabase.table("test_company_banks").insert(data.model_dump()).execute()
    return {"status": "success", "message": "நிறுவன வங்கி கணக்கு சேர்க்கப்பட்டது.", "data": res.data}

@app.delete("/api/admin/company-bank/{bank_id}")
def delete_company_bank(bank_id: int):
    supabase.table("test_company_banks").delete().eq("id", bank_id).execute()
    return {"status": "success", "message": "வங்கி கணக்கு நீக்கப்பட்டது."}

# ==============================================================================
# 💰 தங்கத் தரம் & விலை நிர்ணயம் (Admin Gold Purity & Rate Management APIs)
# ==============================================================================
class GoldPurityRatePayload(BaseModel):
    purity_code: str
    purity_label: str
    rate_per_gram: float
    sort_order: int = 1
    is_active: bool = True

@app.get("/api/admin/gold-purity-rates")
def get_all_gold_purity_rates(include_inactive: bool = False):
    try:
        q = supabase.table("test_gold_purity_rates").select("*")
        if not include_inactive:
            q = q.eq("is_active", True)
        res = q.order("sort_order", desc=False).order("id", desc=False).execute()
        return {"status": "success", "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தங்கத் தரம் பட்டியல் பிழை: {str(e)}")

@app.post("/api/admin/gold-purity-rate/save")
def save_gold_purity_rate(data: GoldPurityRatePayload):
    try:
        code = data.purity_code.strip().upper()
        label = data.purity_label.strip()
        rate = float(data.rate_per_gram or 0)
        if not code or not label or rate <= 0:
            raise HTTPException(status_code=400, detail="தரக் குறியீடு, பெயர் மற்றும் சரியான கிராம் விலையை உள்ளிடவும்.")

        existing = supabase.table("test_gold_purity_rates").select("id").eq("purity_code", code).execute()
        now_t = datetime.now(IST).isoformat()
        payload = {
            "purity_code": code,
            "purity_label": label,
            "rate_per_gram": rate,
            "sort_order": int(data.sort_order or 1),
            "is_active": bool(data.is_active),
            "updated_at": now_t
        }

        if existing.data:
            res = supabase.table("test_gold_purity_rates").update(payload).eq("id", existing.data[0]["id"]).execute()
            msg = f"'{label} ({code})' தரத்தின் விலை ₹{rate:,.2f}/g எனப் புதுப்பிக்கப்பட்டது!"
        else:
            res = supabase.table("test_gold_purity_rates").insert(payload).execute()
            msg = f"புதிய தங்கத் தரம் '{label} ({code})' (₹{rate:,.2f}/g) சேர்க்கப்பட்டது!"

        return {"status": "success", "message": msg, "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தங்க விலை சேமிப்பு பிழை: {str(e)}")

@app.delete("/api/admin/gold-purity-rate/{rate_id}")
def delete_gold_purity_rate(rate_id: int):
    try:
        supabase.table("test_gold_purity_rates").delete().eq("id", rate_id).execute()
        return {"status": "success", "message": "தங்கத் தரம் நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# பழைய /api/admin/gold-rate/today அழைப்புகளைப் புதிய அட்டவணையுடன் இணைத்தல்
@app.get("/api/admin/gold-rate/today")
def get_today_gold_rate():
    try:
        res = supabase.table("test_gold_purity_rates").select("*").eq("is_active", True).order("sort_order", desc=False).execute()
        rates_list = res.data or []
        rate_map = {r["purity_code"].upper(): float(r["rate_per_gram"]) for r in rates_list}
        r_24k = rate_map.get("24K", 0.0)
        r_22k = rate_map.get("916", rate_map.get("22CT", 0.0))
        r_18k = rate_map.get("18CT", 0.0)
        return {
            "status": "success",
            "data": {
                "rate_24k_per_gram": r_24k,
                "rate_22k_per_gram": r_22k,
                "rate_18k_per_gram": r_18k,
                "purity_rates": rates_list
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/branches")
def get_branches():
    res = supabase.table("test_branches").select("*").order("id", desc=True).execute()
    return {"status": "success", "data": res.data or []}

@app.post("/api/admin/branch/create")
def create_branch(data: BranchPayload):
    res = supabase.table("test_branches").insert(data.model_dump()).execute()
    return {"status": "success", "message": "கிளை உருவாக்கப்பட்டது.", "data": res.data}

@app.put("/api/admin/branch/{branch_id}")
def update_branch(branch_id: int, data: BranchPayload):
    supabase.table("test_branches").update(data.model_dump()).eq("id", branch_id).execute()
    return {"status": "success", "message": "கிளை விபரங்கள் புதுப்பிக்கப்பட்டன."}

@app.delete("/api/admin/branch/{branch_id}")
def delete_branch(branch_id: int):
    supabase.table("test_branches").delete().eq("id", branch_id).execute()
    return {"status": "success", "message": "கிளை நீக்கப்பட்டது."}

@app.get("/api/admin/staff")
@app.get("/api/admin/staff/list")
def get_staff_list():
    res = supabase.table("test_staff_users").select("*, test_branches(branch_name)").order("id", desc=True).execute()
    return {"status": "success", "data": res.data or []}

@app.post("/api/admin/staff/create")
def create_staff(data: StaffPayload):
    check = supabase.table("test_staff_users").select("id").eq("username", data.username.strip()).execute()
    if check.data:
        raise HTTPException(status_code=400, detail="இந்தப் பயனர் பெயர் ஏற்கனவே உள்ளது.")
    staff_record = data.model_dump()
    if not staff_record.get("password"):
        staff_record["password"] = "gold123"
    res = supabase.table("test_staff_users").insert(staff_record).execute()
    return {"status": "success", "message": "பணியாளர் கணக்கு உருவாக்கப்பட்டது.", "data": res.data}

@app.put("/api/admin/staff/{staff_id}")
def update_staff(staff_id: int, data: dict):
    try:
        update_dict = {
            "full_name": data.get("full_name"),
            "mobile": data.get("mobile"),
            "role_key": data.get("role_key"),
            "branch_id": data.get("branch_id"),
            "is_active": bool(data.get("is_active", True)),
            "is_branch_manager": bool(data.get("is_branch_manager", False)),
            "can_access_counter": bool(data.get("can_access_counter", False)),
            "can_approve_kyc": bool(data.get("can_approve_kyc", False)),
            "can_approve_updates": bool(data.get("can_approve_updates", False)),
            "can_manage_users": bool(data.get("can_manage_users", False)),
            "can_approve_otp_exempt": bool(data.get("can_approve_otp_exempt", False)),
            "can_approve_expenses": bool(data.get("can_approve_expenses", False)),
            "can_manage_treasury": bool(data.get("can_manage_treasury", False)),
            "can_approve_rebate": bool(data.get("can_approve_rebate", False)),
            "can_manage_gp_stock": bool(data.get("can_manage_gp_stock", False)),
            "can_approve_gss_benefit": bool(data.get("can_approve_gss_benefit", False)),
            "can_access_hq_packets": bool(data.get("can_access_hq_packets", False)),
            "can_approve_hq_packets": bool(data.get("can_approve_hq_packets", False)),
            "can_audit_documents": bool(data.get("can_audit_documents", False)),
        }
        if data.get("password"):
            update_dict["password"] = data.get("password")

        supabase.table("test_staff_users").update(update_dict).eq("id", staff_id).execute()
        return {"status": "success", "message": "பணியாளர் விவரங்கள் வெற்றிகரமாகப் புதுப்பிக்கப்பட்டன!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/staff/{staff_id}")
def delete_staff(staff_id: int):
    supabase.table("test_staff_users").delete().eq("id", staff_id).execute()
    return {"status": "success", "message": "பணியாளர் நீக்கப்பட்டது."}

@app.patch("/api/admin/staff/{staff_id}/toggle-active")
def toggle_staff_active_status(staff_id: int):
    try:
        curr = supabase.table("test_staff_users").select("full_name, is_active").eq("id", staff_id).execute()
        if not curr.data:
            raise HTTPException(status_code=404, detail="பணியாளர் விபரம் கிடைக்கவில்லை.")
        current_active = curr.data[0].get("is_active")
        new_active = False if current_active is not False else True
        supabase.table("test_staff_users").update({"is_active": new_active}).eq("id", staff_id).execute()
        st_txt = "Active (பணியில் உள்ளார்)" if new_active else "Inactive (பணியிலிருந்து நீக்கப்பட்டார்)"
        return {"status": "success", "message": f"{curr.data[0]['full_name']} நிலை '{st_txt}' என மாற்றப்பட்டது!", "is_active": new_active}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bank/request-transfer")
def create_bank_transfer(data: BankTransferPayload):
    record = data.model_dump()
    record["status"] = "PENDING"
    res = supabase.table("test_bank_transfers").insert(record).execute()
    return {"status": "success", "message": "வங்கி பரிவர்த்தனை வேண்டுகோள் தலைமையகத்திற்கு அனுப்பப்பட்டது.", "data": res.data}

@app.get("/api/bank/transfer-status/{transfer_id}")
def get_single_bank_transfer_status(transfer_id: int):
    try:
        res = supabase.table("test_bank_transfers").select("status, receipt_ref_no, company_bank_name").eq("id", transfer_id).execute()
        if res.data:
            return {"status": "success", "transfer_status": res.data[0].get("status", "PENDING"), "data": res.data[0]}
        return {"status": "success", "transfer_status": "PENDING"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bank/branch-status")
def get_branch_bank_status(branch_id: int = Query(...)):
    cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
    cust_map = {c["id"]: c for c in (cust_res.data or [])}
    trans_res = supabase.table("test_bank_transfers").select("*").eq("branch_id", branch_id).order("id", desc=True).limit(20).execute()
    data = trans_res.data or []
    for t in data:
        c = cust_map.get(t.get("customer_id"), {})
        t["test_customers"] = {"name": c.get("name", "வாடிக்கையாளர்"), "mobile": c.get("mobile", "-")}
    return {"status": "success", "data": data}

@app.post("/api/hq/process-bank-transfer")
def process_hq_bank_transfer(data: dict):
    try:
        transfer_id = data.get("transfer_id")
        action = data.get("action")
        admin_id = data.get("admin_id") or 1
        company_bank_id = data.get("company_bank_id")
        utr_ref_no = data.get("utr_ref_no")
        notes = data.get("notes") or ""

        company_bank_name = None
        if company_bank_id:
            try:
                b_res = supabase.table("test_company_banks").select("bank_name, account_no").eq("id", company_bank_id).execute()
                if b_res.data:
                    b_row = b_res.data[0]
                    company_bank_name = f"{b_row.get('bank_name', '')} ({b_row.get('account_no', '')})"
            except Exception as be:
                print("Bank name fetch error:", be)

        now_time = datetime.now(IST).isoformat()
        if action == "REJECT":
            supabase.table("test_bank_transfers").update({
                "status": "REJECTED",
                "hq_notes": notes,
                "approved_by": admin_id,
                "approved_at": now_time
            }).eq("id", transfer_id).execute()
            return {"status": "success", "message": "வங்கிப் பரிவர்த்தனை நிராகரிக்கப்பட்டது."}

        supabase.table("test_bank_transfers").update({
            "status": "APPROVED",
            "company_bank_name": company_bank_name,
            "receipt_ref_no": utr_ref_no,
            "hq_notes": notes,
            "approved_by": admin_id,
            "approved_at": now_time
        }).eq("id", transfer_id).execute()

        if company_bank_id:
            try:
                tr_chk = supabase.table("test_bank_transfers").select("amount, direction").eq("id", transfer_id).execute()
                if tr_chk.data:
                    amount = float(tr_chk.data[0].get("amount") or 0.0)
                    direction = tr_chk.data[0].get("direction")
                    cb_res = supabase.table("test_company_banks").select("*").eq("id", company_bank_id).execute()
                    if cb_res.data:
                        cb_row = cb_res.data[0]
                        for bal_col in ["current_balance", "balance", "opening_balance"]:
                            if bal_col in cb_row:
                                old_bal = float(cb_row.get(bal_col) or 0.0)
                                new_bal = (old_bal - amount) if direction == "PAYOUT" else (old_bal + amount)
                                supabase.table("test_company_banks").update({bal_col: new_bal}).eq("id", company_bank_id).execute()
                                break
            except Exception as b_err:
                print("Company bank balance note (ignored):", b_err)

        return {"status": "success", "message": "வங்கிப் பட்டுவாடா வெற்றிகரமாக உறுதி செய்யப்பட்டு ஒப்புதல் அளிக்கப்பட்டது!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வங்கி ஒப்புதல் பிழை: {str(e)}")

@app.get("/api/hq/all-pending-approvals")
def get_all_pending_approvals():
    cust_map = {}
    branch_map = {}
    try:
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        cust_map = {c["id"]: c for c in (cust_res.data or [])}
        branch_res = supabase.table("test_branches").select("id, branch_name, branch_code").execute()
        branch_map = {b["id"]: b for b in (branch_res.data or [])}
    except Exception:
        pass

    payouts_data, receipts_data, visits_data, kyc_data, updates_data = [], [], [], [], []

    try:
        payouts_res = supabase.table("test_bank_transfers").select("*").eq("direction", "PAYOUT").eq("status", "PENDING").order("id", desc=True).execute()
        payouts_data = payouts_res.data or []
        for p in payouts_data:
            c = cust_map.get(p.get("customer_id"), {})
            p["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{p.get('customer_id')}"), "mobile": c.get("mobile", "-")}
    except Exception:
        pass

    try:
        receipts_res = supabase.table("test_bank_transfers").select("*").eq("direction", "RECEIPT").eq("status", "PENDING").order("id", desc=True).execute()
        receipts_data = receipts_res.data or []
        for r in receipts_data:
            c = cust_map.get(r.get("customer_id"), {})
            r["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{r.get('customer_id')}"), "mobile": c.get("mobile", "-")}
    except Exception:
        pass

    try:
        visits_res = supabase.table("test_customer_visits").select("*").eq("status", "PENDING_HQ").order("id", desc=True).limit(30).execute()
        visits_data = visits_res.data or []
        for v in visits_data:
            c = cust_map.get(v.get("customer_id"), {})
            b = branch_map.get(v.get("branch_id"), {})
            v["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{v.get('customer_id')}"), "mobile": c.get("mobile", "-")}
            v["test_branches"] = {"branch_name": b.get("branch_name", f"கிளை #{v.get('branch_id')}"), "branch_code": b.get("branch_code", "BR")}
    except Exception:
        pass

    try:
        kyc_res = supabase.table("test_customers").select("*").eq("kyc_status", "PENDING").order("id", desc=True).execute()
        kyc_data = kyc_res.data or []
    except Exception:
        pass

    try:
        updates_res = supabase.table("test_customer_update_requests").select("*").eq("status", "PENDING").order("id", desc=True).execute()
        updates_data = updates_res.data or []
        for u in updates_data:
            c = cust_map.get(u.get("customer_id"), {})
            b = branch_map.get(u.get("branch_id"), {})
            u["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{u.get('customer_id')}"), "mobile": c.get("mobile", "-")}
            u["test_branches"] = {"branch_name": b.get("branch_name", f"கிளை #{u.get('branch_id')}"), "branch_code": b.get("branch_code", "BR")}
    except Exception:
        pass

    return {
        "status": "success",
        "pending_kyc": kyc_data,
        "pending_updates": updates_data,
        "pending_visits": visits_data,
        "pending_payouts": payouts_data,
        "pending_receipts": receipts_data
    }

@app.post("/api/hq/approve-kyc")
def process_kyc_approval(data: ApprovalActionPayload):
    try:
        status = "VERIFIED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_customers").update({"kyc_status": status}).eq("id", data.request_id).execute()
        return {"status": "success", "message": f"KYC நிலை '{status}' என மாற்றப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-update")
def process_update_approval(data: ApprovalActionPayload):
    try:
        req_res = supabase.table("test_customer_update_requests").select("*").eq("id", data.request_id).execute()
        if not req_res.data:
            raise HTTPException(status_code=404, detail="கோரிக்கை கிடைக்கவில்லை.")
        req = req_res.data[0]
        new_status = "APPROVED" if data.action == "APPROVE" else "REJECTED"

        if data.action == "APPROVE":
            changes = req.get("requested_changes", {})
            if changes:
                supabase.table("test_customers").update(changes).eq("id", req["customer_id"]).execute()

        try:
            supabase.table("test_customer_update_requests").update({
                "status": new_status,
                "approved_by": data.admin_id,
                "approved_at": "now()"
            }).eq("id", data.request_id).execute()
        except Exception:
            supabase.table("test_customer_update_requests").update({
                "status": new_status
            }).eq("id", data.request_id).execute()

        msg = "சுயவிவர மாற்றம் வெற்றிகரமாக அங்கீகரிக்கப்பட்டது!" if new_status == "APPROVED" else "சுயவிவர மாற்றக் கோரிக்கை நிராகரிக்கப்பட்டது."
        return {"status": "success", "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"சுயவிவர ஒப்புதல் பிழை: {str(e)}")

@app.post("/api/customer/new-full-kyc")
def create_full_kyc(data: FullCustomerKYCPayload):
    try:
        clean_mobile = data.mobile.strip()
        existing = supabase.table("test_customers").select("id, name").eq("mobile", clean_mobile).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail=f"இந்த மொபைல் எண் ஏற்கனவே உள்ளது ({existing.data[0]['name']}).")
        record = data.model_dump()
        record["kyc_status"] = "PENDING"
        record["is_active"] = True
        res = supabase.table("test_customers").insert(record).execute()
        return {"status": "success", "message": "முழு KYC சமர்ப்பிக்கப்பட்டது! தலைமை ஒப்புதலுக்குக் காத்திருக்கிறது.", "data": res.data or []}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KYC பதிவு பிழை: {str(e)}")

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
        return {"status": "success", "message": "விபர மாற்றக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது.", "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கோரிக்கை பதிவு பிழை: {str(e)}")

# ==========================================
# 🔄 உள்-பணப் பரிமாற்றம் & கருவூல மேலாண்மை (Treasury Transfers)
# ==========================================
@app.post("/api/treasury/transfer-request")
def create_treasury_transfer(data: dict):
    try:
        branch_id = data.get("branch_id") or 1
        trans_date = data.get("transaction_date") or datetime.now(IST).strftime("%Y-%m-%d")

        day_chk = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", branch_id)
            .eq("business_date", trans_date)
            .execute()
        )
        if day_chk.data and day_chk.data[0].get("status") == "CLOSED":
            raise HTTPException(
                status_code=400, 
                detail=f"⚠️ {trans_date} நாளுக்கான மாலை கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது!"
            )

        from_src, to_dest = "BRANCH_CASH", "HQ_VAULT"
        transfer_type = data.get("transfer_type")

        if transfer_type == "HQ_TO_BRANCH":
            from_src, to_dest = "HQ_VAULT", "BRANCH_CASH"
        elif transfer_type == "CASH_TO_BANK":
            from_src, to_dest = "BRANCH_CASH", "COMPANY_BANK"
        elif transfer_type == "BANK_TO_CASH":
            from_src, to_dest = "COMPANY_BANK", "BRANCH_CASH"

        rec = {
            "transfer_type": transfer_type,
            "from_source": from_src,
            "to_destination": to_dest,
            "branch_id": branch_id,
            "company_bank_id": data.get("company_bank_id"),
            "amount": float(data.get("amount") or 0.0),
            "carrier_person": data.get("carrier_person"),
            "reference_no": data.get("reference_no"),
            "proof_doc": data.get("proof_doc"),
            "notes": data.get("notes"),
            "status": "PENDING",
            "created_by": data.get("staff_id"),
            "transaction_date": trans_date,
            "created_at": datetime.now(IST).isoformat()
        }
        res = supabase.table("test_treasury_transfers").insert(rec).execute()
        return {"status": "success", "message": "பணப் பரிமாற்றக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது.", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"பரிமாற்றப் பதிவு பிழை: {str(e)}")

@app.get("/api/hq/pending-treasury-transfers")
def get_pending_treasury_transfers():
    try:
        branch_res = supabase.table("test_branches").select("id, branch_name").execute()
        b_map = {b["id"]: b.get("branch_name") for b in (branch_res.data or [])}

        bank_res = supabase.table("test_company_banks").select("id, bank_name, account_no").execute()
        bk_map = {b["id"]: f"{b['bank_name']} ({b['account_no']})" for b in (bank_res.data or [])}

        res = (
            supabase.table("test_treasury_transfers")
            .select("*")
            .eq("status", "PENDING")
            .order("id", desc=True)
            .execute()
        )
        data = res.data or []
        for x in data:
            x["branch_name"] = b_map.get(x.get("branch_id"), f"கிளை #{x.get('branch_id')}")
            if x.get("company_bank_id"):
                x["company_bank_label"] = bk_map.get(x.get("company_bank_id"), "-")

        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-treasury-transfer")
def approve_treasury_transfer(data: TreasuryApprovalPayload):
    try:
        status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
        t_res = supabase.table("test_treasury_transfers").select("*").eq("id", data.transfer_id).execute()
        if not t_res.data:
            raise HTTPException(status_code=404, detail="பரிமாற்ற விபரம் கிடைக்கவில்லை")
        transfer = t_res.data[0]

        if status == "APPROVED" and transfer.get("company_bank_id"):
            amt = float(transfer.get("amount") or 0.0)
            bk_res = supabase.table("test_company_banks").select("*").eq("id", transfer["company_bank_id"]).execute()
            if bk_res.data:
                comp_bank = bk_res.data[0]
                cur_bal = float(comp_bank.get("current_balance") or comp_bank.get("opening_balance") or 0.0)
                if transfer.get("transfer_type") == "CASH_TO_BANK":
                    new_bal = cur_bal + amt
                elif transfer.get("transfer_type") == "BANK_TO_CASH":
                    new_bal = cur_bal - amt
                else:
                    new_bal = cur_bal
                supabase.table("test_company_banks").update({"current_balance": new_bal}).eq("id", transfer["company_bank_id"]).execute()

        supabase.table("test_treasury_transfers").update({
            "status": status,
            "approved_by": data.admin_id,
            "approved_at": "now()"
        }).eq("id", data.transfer_id).execute()

        return {"status": "success", "message": f"பரிமாற்றம் வெற்றிகரமாக '{status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 🏷️ வட்டி தள்ளுபடி (Interest Rebate) ஒப்புதல் மையம்
# ==========================================
@app.post("/api/rebate/request")
def request_interest_rebate(data: dict):
    try:
        rec = {
            "visit_id": data.get("visit_id"),
            "loan_id": data.get("loan_id"),
            "loan_no": data.get("loan_no"),
            "customer_id": data.get("customer_id"),
            "branch_id": data.get("branch_id") or 1,
            "calculated_interest": float(data.get("calculated_interest") or 0),
            "requested_rebate": float(data.get("requested_rebate") or 0),
            "reason": data.get("reason") or "வட்டி தள்ளுபடி கோரிக்கை",
            "status": "PENDING",
            "requested_by": data.get("staff_id") or 1
        }
        res = supabase.table("test_rebate_approvals").insert(rec).execute()
        req_id = res.data[0]["id"] if res.data else None
        return {"status": "success", "request_id": req_id, "message": "வட்டி தள்ளுபடி ஒப்புதலுக்கு அனுப்பப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rebate/status/{req_id}")
def check_rebate_status(req_id: int):
    try:
        res = supabase.table("test_rebate_approvals").select("status").eq("id", req_id).execute()
        status = res.data[0]["status"] if res.data else "PENDING"
        return {"status": "success", "approval_status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hq/pending-rebates")
def get_pending_rebates():
    try:
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        c_map = {c["id"]: c for c in (cust_res.data or [])}

        br_res = supabase.table("test_branches").select("id, branch_name").execute()
        b_map = {b["id"]: b.get("branch_name") for b in (br_res.data or [])}

        res = supabase.table("test_rebate_approvals").select("*").eq("status", "PENDING").order("id", desc=True).execute()
        data = res.data or []
        for r in data:
            c = c_map.get(r.get("customer_id"), {})
            r["customer_name"] = c.get("name", "-")
            r["customer_mobile"] = c.get("mobile", "-")
            r["branch_name"] = b_map.get(r.get("branch_id"), f"கிளை #{r.get('branch_id')}")
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-rebate")
def approve_rebate_request(data: dict):
    try:
        req_id = data.get("request_id")
        action = data.get("action")
        admin_id = data.get("admin_id") or 1
        new_status = "APPROVED" if action == "APPROVE" else "REJECTED"

        supabase.table("test_rebate_approvals").update({
            "status": new_status,
            "approved_by": admin_id,
            "approved_at": datetime.now(IST).isoformat()
        }).eq("id", req_id).execute()

        return {"status": "success", "message": f"வட்டி தள்ளுபடி கோரிக்கை '{new_status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 🪙 நகை வாங்குதல் (GP) & நகை விற்பனை (GS) API-கள்
# ==========================================
@app.get("/api/gp/next-no")
def get_next_gp_no(branch_id: int = Query(...)):
    try:
        branch_res = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        branch_code = branch_res.data[0]["branch_code"].strip().upper() if branch_res.data else "BR"
        count_res = supabase.table("test_gold_purchases").select("id", count="exact").eq("branch_id", branch_id).execute()
        next_count = (count_res.count or len(count_res.data or [])) + 1
        return {"status": "success", "branch_code": branch_code, "next_gp_no": f"{branch_code}/GP/{next_count:04d}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GP எண் பிழை: {str(e)}")

@app.get("/api/gs/next-no")
def get_next_gs_no(branch_id: int = Query(...)):
    try:
        branch_res = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        branch_code = branch_res.data[0]["branch_code"].strip().upper() if branch_res.data else "BR"
        count_res = supabase.table("test_gold_sales").select("id", count="exact").eq("branch_id", branch_id).execute()
        next_count = (count_res.count or len(count_res.data or [])) + 1
        return {"status": "success", "branch_code": branch_code, "next_gs_no": f"{branch_code}/GS/{next_count:04d}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GS எண் பிழை: {str(e)}")

@app.get("/api/gs/branch-stock")
def get_branch_sale_stock(branch_id: int = Query(...)):
    try:
        res = (
            supabase.table("test_gold_purchase_items")
            .select("*")
            .eq("stock_status", "ALLOCATED_FOR_SALE")
            .eq("allocated_branch_id", branch_id)
            .order("id", desc=False)
            .execute()
        )
        return {"status": "success", "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gss/next-no")
def get_next_gss_no(branch_id: int = Query(...)):
    try:
        branch_res = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        branch_code = branch_res.data[0]["branch_code"].strip().upper() if branch_res.data else "BR"
        count_res = supabase.table("test_customer_savings_accounts").select("id", count="exact").eq("branch_id", branch_id).execute()
        next_count = (count_res.count or len(count_res.data or [])) + 1
        return {"status": "success", "branch_code": branch_code, "next_gss_no": f"{branch_code}/GSS/{next_count:04d}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GSS எண் பிழை: {str(e)}")

@app.get("/api/customer/{customer_id}/gss-accounts")
def get_customer_gss_accounts(customer_id: int):
    try:
        sch_res = supabase.table("test_savings_schemes").select("*").execute()
        sch_map = {s["id"]: s for s in (sch_res.data or [])}

        acc_res = (
            supabase.table("test_customer_savings_accounts")
            .select("*")
            .eq("customer_id", customer_id)
            .eq("status", "ACTIVE")
            .order("id", desc=False)
            .execute()
        )
        accounts = acc_res.data or []
        for acc in accounts:
            acc["scheme_details"] = sch_map.get(acc.get("scheme_id"), {})
            txn_res = (
                supabase.table("test_savings_transactions")
                .select("*")
                .eq("account_id", acc["id"])
                .order("id", desc=False)
                .execute()
            )
            acc["transactions"] = txn_res.data or []

        return {"status": "success", "data": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gss/request-maturity-benefit")
def request_gss_maturity_benefit(data: dict):
    try:
        acc_id = int(data.get("account_id"))
        proposed_amt = float(data.get("proposed_benefit") or 0)
        supabase.table("test_customer_savings_accounts").update({
            "proposed_benefit_amount": proposed_amt,
            "benefit_approval_status": "PENDING"
        }).eq("id", acc_id).execute()
        return {"status": "success", "message": "மெச்சியுரிட்டி பெனிபிட் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hq/pending-gss-benefits")
def get_pending_gss_benefits():
    try:
        acc_res = supabase.table("test_customer_savings_accounts").select("*").eq("benefit_approval_status", "PENDING").execute()
        accounts = acc_res.data or []
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        cust_map = {c["id"]: c for c in (cust_res.data or [])}
        br_res = supabase.table("test_branches").select("id, branch_name").execute()
        br_map = {b["id"]: b["branch_name"] for b in (br_res.data or [])}
        sch_res = supabase.table("test_savings_schemes").select("id, scheme_name").execute()
        sch_map = {s["id"]: s["scheme_name"] for s in (sch_res.data or [])}

        for a in accounts:
            c = cust_map.get(a.get("customer_id"), {})
            a["customer_name"] = c.get("name", "-")
            a["customer_mobile"] = c.get("mobile", "-")
            a["branch_name"] = br_map.get(a.get("branch_id"), "-")
            a["scheme_name"] = sch_map.get(a.get("scheme_id"), "GSS")
        return {"status": "success", "data": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-gss-benefit")
def approve_gss_benefit(data: dict):
    try:
        acc_id = int(data.get("account_id"))
        action = data.get("action")
        edited_amt = float(data.get("approved_amount") or 0)
        if action == "APPROVE":
            supabase.table("test_customer_savings_accounts").update({
                "approved_benefit_amount": edited_amt,
                "benefit_approval_status": "APPROVED"
            }).eq("id", acc_id).execute()
            return {"status": "success", "message": f"₹{edited_amt} மெச்சியுரிட்டி பெனிபிட் அங்கீகரிக்கப்பட்டது!"}
        else:
            supabase.table("test_customer_savings_accounts").update({
                "benefit_approval_status": "REJECTED"
            }).eq("id", acc_id).execute()
            return {"status": "success", "message": "பெனிபிட் கோரிக்கை நிராகரிக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/gss-schemes")
def get_gss_schemes():
    try:
        res = supabase.table("test_savings_schemes").select("*").eq("is_active", True).order("id", desc=True).execute()
        return {"status": "success", "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/gss-scheme/create")
def create_gss_scheme(data: dict):
    try:
        code = str(data.get("scheme_code") or "").strip().upper()
        check = supabase.table("test_savings_schemes").select("id").eq("scheme_code", code).execute()
        if check.data:
            raise HTTPException(status_code=400, detail="இந்தத் திட்டக் குறியீடு ஏற்கனவே உள்ளது.")

        rec = {
            "scheme_code": code,
            "scheme_name": str(data.get("scheme_name") or "").strip(),
            "calculation_type": data.get("calculation_type", "FIXED_AMOUNT"),
            "frequency": data.get("frequency", "MONTHLY"),
            "installment_amount": float(data.get("installment_amount") or 0),
            "tenure_limit_type": data.get("tenure_limit_type", "LIMITED"),
            "tenure_count": int(data.get("tenure_count") or 12),
            "grace_period_days": int(data.get("grace_period_days") or 5),
            "penalty_per_thousand": float(data.get("penalty_per_thousand") if data.get("penalty_per_thousand") is not None else 1.0),
            "is_active": True
        }
        res = supabase.table("test_savings_schemes").insert(rec).execute()
        return {"status": "success", "message": "புதிய நகை சேமிப்புத் திட்டம் உருவாக்கப்பட்டது!", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/gss-scheme/{scheme_id}")
def delete_gss_scheme(scheme_id: int):
    try:
        supabase.table("test_savings_schemes").delete().eq("id", scheme_id).execute()
        return {"status": "success", "message": "திட்டம் நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 📦 GP நகை இருப்பு & தலைமையக ஒதுக்கீடு (Stock Flow APIs)
# ==========================================
@app.get("/api/gp/branch-purchased-stock")
def get_branch_purchased_stock(branch_id: int = Query(...)):
    try:
        p_res = supabase.table("test_gold_purchases").select("id, gp_no, transaction_date").eq("branch_id", branch_id).execute()
        p_map = {p["id"]: p for p in (p_res.data or [])}
        if not p_map:
            return {"status": "success", "data": []}

        items_res = (
            supabase.table("test_gold_purchase_items")
            .select("*")
            .in_("purchase_id", list(p_map.keys()))
            .eq("stock_status", "AT_BRANCH")
            .order("id", desc=False)
            .execute()
        )
        data = items_res.data or []
        for x in data:
            p = p_map.get(x.get("purchase_id"), {})
            x["gp_no"] = p.get("gp_no", "-")
            x["purchase_date"] = p.get("transaction_date", "-")
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gp/send-to-hq")
def send_gp_items_to_hq(data: dict):
    try:
        item_ids = data.get("item_ids") or []
        if not item_ids:
            raise HTTPException(status_code=400, detail="அனுப்ப வேண்டிய நகைகளைத் தேர்வு செய்யவும்.")
        supabase.table("test_gold_purchase_items").update({"stock_status": "SENT_TO_HQ"}).in_("id", item_ids).execute()
        return {"status": "success", "message": f"{len(item_ids)} நகைகள் தலைமையகத்திற்கு வெற்றிகரமாக அனுப்பப்பட்டன!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hq/gp-stock-list")
def get_hq_gp_stock_list():
    try:
        br_res = supabase.table("test_branches").select("id, branch_name, branch_code").execute()
        b_map = {b["id"]: b for b in (br_res.data or [])}

        p_res = supabase.table("test_gold_purchases").select("id, gp_no, branch_id, transaction_date").execute()
        p_map = {p["id"]: p for p in (p_res.data or [])}

        items_res = (
            supabase.table("test_gold_purchase_items")
            .select("*")
            .in_("stock_status", ["SENT_TO_HQ", "ALLOCATED_FOR_SALE"])
            .order("id", desc=True)
            .execute()
        )
        data = items_res.data or []
        for x in data:
            p = p_map.get(x.get("purchase_id"), {})
            b = b_map.get(p.get("branch_id"), {})
            alloc_b = b_map.get(x.get("allocated_branch_id"), {})
            x["gp_no"] = p.get("gp_no", "-")
            x["purchase_date"] = p.get("transaction_date", "-")
            x["from_branch_name"] = b.get("branch_name", "-")
            x["allocated_branch_name"] = alloc_b.get("branch_name", "-")
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/allocate-stock-for-sale")
def allocate_stock_for_sale(data: dict):
    try:
        item_id = data.get("item_id")
        target_branch_id = data.get("allocated_branch_id")
        sell_rate = float(data.get("selling_rate_per_gram") or 0)
        making_chg = float(data.get("making_charge") or 0)
        gst_pct = float(data.get("gst_percent") if data.get("gst_percent") is not None else 3.0)

        if not item_id or not target_branch_id or sell_rate <= 0:
            raise HTTPException(status_code=400, detail="கிளை மற்றும் விற்பனை கிராம் விலையைச் சரியாக உள்ளிடவும்.")

        supabase.table("test_gold_purchase_items").update({
            "stock_status": "ALLOCATED_FOR_SALE",
            "allocated_branch_id": int(target_branch_id),
            "selling_rate_per_gram": sell_rate,
            "making_charge": making_chg,
            "gst_percent": gst_pct
        }).eq("id", item_id).execute()

        return {"status": "success", "message": "நகை விற்பனைக்காகக் கிளைக்கு வெற்றிகரமாக ஒதுக்கப்பட்டது!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# கூடையில் இருந்து நகைக்கடனை நீக்கும் API (Undo Cart Item)
@app.delete("/api/loan/{loan_id}")
def delete_pawn_loan_from_cart(loan_id: int):
    try:
        supabase.table("test_gold_packets").delete().eq("loan_id", loan_id).execute()
        supabase.table("test_gold_loan_items").delete().eq("loan_id", loan_id).execute()
        supabase.table("test_gold_loans").delete().eq("id", loan_id).execute()
        return {"status": "success", "message": "கடன் நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================================================================
# 💎 STANDARD INVESTMENT (SI / FD) API ENDPOINTS
# =========================================================================
@app.get("/api/admin/si-schemes")
def get_si_schemes():
    try:
        res = supabase.table("test_si_schemes").select("*").eq("is_active", True).order("id", desc=True).execute()
        return {"status": "success", "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/si-scheme/create")
def create_si_scheme(data: dict):
    try:
        rec = {
            "scheme_code": str(data.get("scheme_code") or "").strip().upper(),
            "scheme_name": str(data.get("scheme_name") or "").strip(),
            "tenure_value": int(data.get("tenure_value") or 12),
            "tenure_unit": str(data.get("tenure_unit") or "MONTH"),
            "locking_period_months": int(data.get("locking_period_months") or 0),
            "min_amount": float(data.get("min_amount") or 10000),
            "return_calc_type": str(data.get("return_calc_type") or "SIMPLE"),
            "return_calc_period": str(data.get("return_calc_period") or "MONTH"),
            "payout_frequency": str(data.get("payout_frequency") or "MONTHLY"),
            "return_rate": float(data.get("return_rate") or 0),
            "preclose_slabs": data.get("preclose_slabs") or [],
            "periodic_return_per_lakh": float(data.get("periodic_return_per_lakh") or 0),
            "maturity_amount_per_lakh": float(data.get("maturity_amount_per_lakh") or 0),
            "is_active": True
        }
        res = supabase.table("test_si_schemes").insert(rec).execute()
        return {"status": "success", "message": "புதிய Standard Investment (SI) திட்டம் உருவாக்கப்பட்டது!", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/si-scheme/{scheme_id}")
def delete_si_scheme(scheme_id: int):
    try:
        supabase.table("test_si_schemes").update({"is_active": False}).eq("id", scheme_id).execute()
        return {"status": "success", "message": "SI திட்டம் நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/si/next-no")
def get_next_si_no(branch_id: int = 1):
    try:
        br = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        b_code = br.data[0]["branch_code"] if br.data else "BR"
        res = supabase.table("test_si_accounts").select("id").order("id", desc=True).limit(1).execute()
        next_num = (res.data[0]["id"] + 1) if res.data else 1
        return {"status": "success", "next_si_no": f"{b_code}/SI/{str(next_num).zfill(4)}"}
    except Exception:
        return {"status": "success", "next_si_no": "BR/SI/0001"}

@app.get("/api/customer/{customer_id}/si-accounts")
def get_customer_si_accounts(customer_id: int):
    try:
        res = supabase.table("test_si_accounts").select("*, test_si_schemes(*)").eq("customer_id", customer_id).eq("status", "ACTIVE").order("id", desc=True).execute()
        accounts = res.data or []
        for acc in accounts:
            acc["scheme_details"] = acc.get("test_si_schemes") or {}
            p_res = supabase.table("test_si_return_payouts").select("*").eq("si_account_id", acc["id"]).order("id", desc=False).execute()
            acc["payouts"] = p_res.data or []
        return {"status": "success", "data": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/si/request-closure")
def request_si_closure(data: dict):
    try:
        acc_id = int(data.get("account_id"))
        closure_type = str(data.get("closure_type") or "MATURITY")
        prop_prin = float(data.get("proposed_principal") or 0)
        prop_ben = float(data.get("proposed_benefit") or 0)
        supabase.table("test_si_accounts").update({
            "closure_type": closure_type,
            "approval_status": "PENDING",
            "proposed_principal": prop_prin,
            "proposed_benefit": prop_ben
        }).eq("id", acc_id).execute()
        return {"status": "success", "message": "SI கணக்கு முடிப்பு / ப்ரீ-குளோஸ் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hq/pending-si-approvals")
def get_pending_si_approvals():
    try:
        res = supabase.table("test_si_accounts").select("*, test_customers(name, mobile), test_branches(branch_name), test_si_schemes(scheme_name)").eq("approval_status", "PENDING").execute()
        out = []
        for r in (res.data or []):
            out.append({
                "id": r["id"],
                "si_no": r.get("si_no"),
                "closure_type": r.get("closure_type", "MATURITY"),
                "branch_name": (r.get("test_branches") or {}).get("branch_name", "-"),
                "customer_name": (r.get("test_customers") or {}).get("name", "-"),
                "customer_mobile": (r.get("test_customers") or {}).get("mobile", "-"),
                "scheme_name": (r.get("test_si_schemes") or {}).get("scheme_name", "SI"),
                "principal_amount": r.get("principal_amount", 0),
                "total_return_paid": r.get("total_return_paid", 0),
                "proposed_principal": r.get("proposed_principal", 0),
                "proposed_benefit": r.get("proposed_benefit", 0)
            })
        return {"status": "success", "data": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-si-closure")
def approve_si_closure(data: dict):
    try:
        acc_id = int(data.get("account_id"))
        action = data.get("action")
        app_prin = float(data.get("approved_principal") or 0)
        app_ben = float(data.get("approved_benefit") or 0)
        if action == "APPROVE":
            supabase.table("test_si_accounts").update({
                "approval_status": "APPROVED",
                "approved_principal": app_prin,
                "approved_benefit": app_ben
            }).eq("id", acc_id).execute()
            return {"status": "success", "message": f"SI அனுமதி வழங்கப்பட்டது! (அசல்: ₹{app_prin}, பெனிபிட்: ₹{app_ben})"}
        else:
            supabase.table("test_si_accounts").update({
                "approval_status": "REJECTED"
            }).eq("id", acc_id).execute()
            return {"status": "success", "message": "SI கோரிக்கை நிராகரிக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# 📋 DOCUMENT CHECKLIST MASTER (SCHEME-WISE) & FAST AUDIT APIs (50-50 Pagination)
# ==============================================================================
import re

def extract_visit_action_items(actions_summary: str):
    """
    வருகை சுருக்கத்திலிருந்து தனித்தனி நடவடிக்கைகளையும் அவற்றின் எண்களையும் (GL No, GP No, RD No...) பிரித்தெடுத்தல்
    """
    summary = actions_summary or ""
    parts = [p.strip() for p in summary.split(",") if p.strip()]
    extracted = []

    for p in parts:
        low = p.lower()
        # அடைப்புக்குறிக்குள் உள்ள எண் எடுத்தல்: எ.கா: நகைக்கடன் (AVL/0050) -> AVL/0050
        m = re.search(r'\(([^)]+)\)', p)
        ref_val = m.group(1).strip() if m else "-"

        if "நகைக்கடன் (" in low or "new loan" in low or "pledge" in low:
            extracted.append({"activity_type": "GL_NEW", "ref_no": ref_val})
        elif "முழு கடன் முடிப்பு" in low or "closure" in low:
            extracted.append({"activity_type": "GL_CLOSE", "ref_no": ref_val})
        elif "வட்டி வரவு" in low or "பகுதி அசல்" in low:
            extracted.append({"activity_type": "GL_PART_PRINCIPAL", "ref_no": ref_val})
        elif "நகை வாங்குதல்" in low or "/gp/" in low:
            extracted.append({"activity_type": "OLD_GOLD", "ref_no": ref_val})
        elif "நகை விற்பனை" in low or "/gs/" in low:
            extracted.append({"activity_type": "GOLD_SALE", "ref_no": ref_val})
        elif "gss" in low:
            extracted.append({"activity_type": "GSS", "ref_no": ref_val})
        elif "rd" in low:
            extracted.append({"activity_type": "RD", "ref_no": ref_val})
        elif "si " in low or "/si/" in low:
            extracted.append({"activity_type": "SI", "ref_no": ref_val})

    if not extracted:
        extracted.append({"activity_type": "GL_NEW", "ref_no": "-"})
    return extracted

@app.post("/api/hq/approve-visit")
def process_visit_approval(data: ApprovalActionPayload):
    try:
        if data.action != "APPROVE":
            supabase.table("test_customer_visits").update({
                "status": "REJECTED",
                "audit_status": "REJECTED"
            }).eq("id", data.request_id).execute()

            # ❌ நிராகரிக்கப்பட்ட வருகையின் கடன், பாக்கெட், GP ஆகியவற்றை CANCELLED ஆக்குதல்
            try:
                rej_loans = supabase.table("test_gold_loans").select("id").eq("visit_id", data.request_id).execute().data or []
                if rej_loans:
                    loan_ids = [l["id"] for l in rej_loans]
                    supabase.table("test_gold_loans").update({"status": "CANCELLED"}).in_("id", loan_ids).execute()
                    supabase.table("test_gold_packets").update({"packet_status": "CANCELLED"}).in_("loan_id", loan_ids).execute()
                supabase.table("test_gold_purchases").update({"status": "CANCELLED"}).eq("visit_id", data.request_id).execute()
            except Exception as cancel_err:
                print("Auto-cancel note:", cancel_err)

            return {"status": "success", "message": "வருகை நிராகரிக்கப்பட்டு, அதன் நடவடிக்கை எண்கள் ரத்து (CANCELLED) செய்யப்பட்டன."}

        v_res = supabase.table("test_customer_visits").select("*").eq("id", data.request_id).execute()
        if not v_res.data:
            raise HTTPException(status_code=404, detail="வருகை விபரம் கிடைக்கவில்லை.")
        visit = v_res.data[0]

        # 1. அனைத்து ஆவண விதிகளையும், திட்டக் குறியீடுகளையும் எடுத்தல்
        all_rules = supabase.table("test_audit_document_rules").select("*").execute().data or []
        sch_res = supabase.table("test_loan_schemes").select("scheme_name, scheme_code").execute().data or []
        scheme_name_to_code = {s["scheme_name"]: s["scheme_code"] for s in sch_res}

        # இந்த வருகையில் உள்ள நகைக்கடன்களின் திட்டக் குறியீடுகளை எடுத்தல்
        loans_res = supabase.table("test_gold_loans").select("loan_no, scheme_name").eq("visit_id", visit["id"]).execute().data or []
        loan_no_to_scheme_code = {l["loan_no"]: scheme_name_to_code.get(l.get("scheme_name"), "ALL") for l in loans_res}

        action_items = extract_visit_action_items(visit.get("actions_summary") or "")
        docs_payload = []

        for item in action_items:
            act = item["activity_type"]
            ref = item["ref_no"]
            target_scheme_code = loan_no_to_scheme_code.get(ref, "ALL") if act == "GL_NEW" else "ALL"

            for r in all_rules:
                if r["activity_type"] != act:
                    continue
                rule_sch = str(r.get("scheme_code") or "ALL").strip().upper()
                # பொதுவான விதி (ALL) அல்லது குறிப்பிட்ட திட்ட விதி பொருந்தினால் சேர்த்தல்
                if rule_sch == "ALL" or rule_sch == str(target_scheme_code).upper():
                    docs_payload.append({
                        "visit_id": visit["id"],
                        "branch_id": visit.get("branch_id") or 1,
                        "customer_id": visit.get("customer_id"),
                        "transaction_date": visit.get("transaction_date"),
                        "activity_type": act,
                        "ref_no": ref,
                        "document_name": r["document_name"],
                        "doc_status": "PENDING_UPLOAD"
                    })

        if docs_payload:
            supabase.table("test_visit_audit_documents").insert(docs_payload).execute()
            new_audit_st = "DOCS_PENDING"
            msg = f"வருகை அங்கீகரிக்கப்பட்டது! கிளை இணைக்க வேண்டிய {len(docs_payload)} ஆவணங்கள் பட்டியலிடப்பட்டன."
        else:
            new_audit_st = "AUDITED"
            msg = "வருகை அங்கீகரிக்கப்பட்டு தணிக்கை நிறைவடைந்தது."

        supabase.table("test_customer_visits").update({
            "status": "VERIFIED",
            "audit_status": new_audit_st
        }).eq("id", data.request_id).execute()

        return {"status": "success", "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/audit-doc-rules")
def get_audit_doc_rules():
    res = supabase.table("test_audit_document_rules").select("*").order("activity_type").order("id").execute()
    return {"status": "success", "data": res.data or []}

@app.post("/api/admin/audit-doc-rule/create")
def create_audit_doc_rule(data: dict):
    act = str(data.get("activity_type") or "").strip()
    doc_name = str(data.get("document_name") or "").strip()
    sch_code = str(data.get("scheme_code") or "ALL").strip().upper()
    if not act or not doc_name:
        raise HTTPException(status_code=400, detail="நடவடிக்கை மற்றும் ஆவணத்தின் பெயரை உள்ளிடவும்.")
    supabase.table("test_audit_document_rules").insert({
        "activity_type": act,
        "scheme_code": sch_code if act == "GL_NEW" else "ALL",
        "document_name": doc_name
    }).execute()
    return {"status": "success", "message": "புதிய ஆவண விதி சேர்க்கப்பட்டது!"}

@app.delete("/api/admin/audit-doc-rule/{rule_id}")
def delete_audit_doc_rule(rule_id: int):
    supabase.table("test_audit_document_rules").delete().eq("id", rule_id).execute()
    return {"status": "success", "message": "ஆவண விதி நீக்கப்பட்டது."}

@app.get("/api/audit/visits")
def get_audit_visits_list(
    branch_id: int = 0,
    txn_date: str = "",
    audit_status: str = "ALL",
    search: str = "",
    page: int = 1,
    page_size: int = 50
):
    """
    ⚡ அதிவேக API: படங்களை (doc_file_url) தவிர்த்து 50-50 வருகைகளாகப் பிரித்துக் கொடுக்கும்
    """
    try:
        # 1. நிலை வாரியான எண்ணிக்கை (Summary Counts)
        cnt_q = supabase.table("test_customer_visits").select("id, audit_status").eq("status", "VERIFIED")
        if branch_id and branch_id > 0:
            cnt_q = cnt_q.eq("branch_id", branch_id)
        if txn_date:
            cnt_q = cnt_q.eq("transaction_date", txn_date)
        all_status_rows = cnt_q.limit(5000).execute().data or []

        counts = {
            "DOCS_PENDING": sum(1 for r in all_status_rows if r.get("audit_status") == "DOCS_PENDING"),
            "AUDIT_PENDING": sum(1 for r in all_status_rows if r.get("audit_status") == "AUDIT_PENDING"),
            "QUERY_RAISED": sum(1 for r in all_status_rows if r.get("audit_status") == "QUERY_RAISED"),
            "AUDITED": sum(1 for r in all_status_rows if r.get("audit_status") == "AUDITED"),
        }

        # 2. தேடல் & நிலை வடிகட்டி
        q = supabase.table("test_customer_visits").select("*", count="exact").eq("status", "VERIFIED")
        if branch_id and branch_id > 0:
            q = q.eq("branch_id", branch_id)
        if txn_date:
            q = q.eq("transaction_date", txn_date)
        if audit_status and audit_status != "ALL":
            q = q.eq("audit_status", audit_status)

        clean_search = search.strip()
        if clean_search:
            if clean_search.isdigit():
                q = q.eq("id", int(clean_search))
            else:
                q = q.ilike("actions_summary", f"%{clean_search}%")

        offset = max(0, (page - 1) * page_size)
        res = q.order("id", desc=True).range(offset, offset + page_size - 1).execute()
        visits = res.data or []
        total_count = res.count or len(visits)

        if not visits:
            return {"status": "success", "data": [], "total": 0, "counts": counts}

        cust_ids = list({v["customer_id"] for v in visits if v.get("customer_id")})
        c_map = {}
        if cust_ids:
            c_res = supabase.table("test_customers").select("id, name, mobile").in_("id", cust_ids).execute().data or []
            c_map = {c["id"]: c for c in c_res}

        br_res = supabase.table("test_branches").select("id, branch_name").execute().data or []
        b_map = {b["id"]: b.get("branch_name") for b in br_res}

        visit_ids = [v["id"] for v in visits]
        # ⚡ வேகத்திற்காக இங்கே doc_file_url (கனமான படம்) எடுக்கப்படவில்லை!
        d_res = supabase.table("test_visit_audit_documents").select("id, visit_id, doc_status").in_("visit_id", visit_ids).execute().data or []
        doc_count_map = {}
        for d in d_res:
            doc_count_map[d["visit_id"]] = doc_count_map.get(d["visit_id"], 0) + 1

        for v in visits:
            v["customer_name"] = c_map.get(v.get("customer_id"), {}).get("name", "-")
            v["customer_mobile"] = c_map.get(v.get("customer_id"), {}).get("mobile", "-")
            v["branch_name"] = b_map.get(v.get("branch_id"), f"கிளை #{v.get('branch_id')}")
            v["doc_count"] = doc_count_map.get(v["id"], 0)

        return {"status": "success", "data": visits, "total": total_count, "counts": counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audit/visit/{visit_id}/documents")
def get_single_visit_audit_documents(visit_id: int):
    """
    குறிப்பிட்ட ஒரு வருகையைத் திறக்கும்போது மட்டுமே அதன் ஆவணப் படங்களை லோடு செய்தல் (Lazy Load)
    """
    try:
        v_res = supabase.table("test_customer_visits").select("*").eq("id", visit_id).execute()
        if not v_res.data:
            raise HTTPException(status_code=404, detail="வருகை இல்லை")
        visit = v_res.data[0]

        c_res = supabase.table("test_customers").select("name, mobile").eq("id", visit["customer_id"]).execute()
        cust = c_res.data[0] if c_res.data else {}

        b_res = supabase.table("test_branches").select("branch_name").eq("id", visit["branch_id"]).execute()
        br = b_res.data[0] if b_res.data else {}

        docs = supabase.table("test_visit_audit_documents").select("*").eq("visit_id", visit_id).order("id").execute().data or []

        return {
            "status": "success",
            "visit": {
                **visit,
                "customer_name": cust.get("name", "-"),
                "customer_mobile": cust.get("mobile", "-"),
                "branch_name": br.get("branch_name", "-")
            },
            "documents": docs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audit/branch-upload-docs")
def branch_upload_audit_docs(data: dict):
    try:
        visit_id = int(data.get("visit_id"))
        updates = data.get("docs") or []
        staff_id = int(data.get("staff_id") or 1)
        now_t = datetime.now(IST).isoformat()

        for item in updates:
            upd = {"updated_at": now_t, "uploaded_by": staff_id}
            if item.get("doc_file_url"):
                upd["doc_file_url"] = item["doc_file_url"]
                upd["doc_status"] = "UPLOADED"
            if item.get("branch_reply") is not None:
                upd["branch_reply"] = item["branch_reply"]
                if not item.get("doc_file_url"):
                    upd["doc_status"] = "UPLOADED"
            supabase.table("test_visit_audit_documents").update(upd).eq("id", item["id"]).execute()

        chk = supabase.table("test_visit_audit_documents").select("doc_status").eq("visit_id", visit_id).execute()
        all_docs = chk.data or []
        if all(d.get("doc_status") in ["UPLOADED", "APPROVED"] for d in all_docs):
            supabase.table("test_customer_visits").update({"audit_status": "AUDIT_PENDING"}).eq("id", visit_id).execute()
            return {"status": "success", "message": "✅ அனைத்து ஆவணங்களும் அகத்தணிக்கையருக்கு அனுப்பப்பட்டன!"}

        return {"status": "success", "message": "பதிவேற்றிய ஆவணங்கள் சேமிக்கப்பட்டன. மீதமுள்ள ஆவணங்களையும் இணைக்கவும்."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audit/auditor-review")
def auditor_review_visit_docs(data: dict):
    try:
        visit_id = int(data.get("visit_id"))
        reviews = data.get("reviews") or []
        auditor_id = int(data.get("auditor_id") or 1)
        now_t = datetime.now(IST).isoformat()

        has_query = False
        for r in reviews:
            if r.get("action") == "QUERY":
                has_query = True
                supabase.table("test_visit_audit_documents").update({
                    "doc_status": "QUERY",
                    "auditor_query": r.get("query_text") or "ஆவணம் தெளிவாக இல்லை / சரிபார்க்கவும்",
                    "audited_by": auditor_id,
                    "updated_at": now_t
                }).eq("id", r["id"]).execute()
            else:
                supabase.table("test_visit_audit_documents").update({
                    "doc_status": "APPROVED",
                    "audited_by": auditor_id,
                    "updated_at": now_t
                }).eq("id", r["id"]).execute()

        new_status = "QUERY_RAISED" if has_query else "AUDITED"
        supabase.table("test_customer_visits").update({"audit_status": new_status}).eq("id", visit_id).execute()
        msg = "❓ தணிக்கை கேள்வி (Query) கிளைக்கு அனுப்பப்பட்டது!" if has_query else "✅ தணிக்கை அனுமதி வழங்கப்பட்டு நடவடிக்கை முடிவு செய்யப்பட்டது!"
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ==============================================================================
# 🔎 தலைமையகத்தின் 360° முழு பரிவர்த்தனை வரலாற்றுத் தேடல் API (HQ 360° Master Audit Search)
# ==============================================================================
@app.get("/api/hq/master-audit-search")
def hq_master_audit_search(query: str = Query(..., min_length=1)):
    """
    கடன் எண் (AVL/0050), GP/GS/GSS/RD/SI எண், வருகை எண் (#VIS-186) அல்லது மொபைல் எண் மூலம்
    ஆரம்பம் முதல் இன்று வரையிலான 360° முழு வரலாற்றையும் திரட்டிக் கொடுக்கும் API.
    """
    try:
        q = query.strip()
        q_upper = q.upper()

        # 1. பணியாளர்கள் & கிளைகள் பெயர் அகராதி (Staff & Branch Map)
        staff_res = supabase.table("test_staff_users").select("id, full_name, role_key").execute().data or []
        s_map = {s["id"]: f"{s['full_name']} ({s.get('role_key', '')})" for s in staff_res}

        br_res = supabase.table("test_branches").select("id, branch_name, branch_code").execute().data or []
        b_map = {b["id"]: b.get("branch_name", "-") for b in br_res}

        customer = None
        customer_id = None
        visit = None
        matched_loan = None
        matched_packet = None
        extra_record = None
        record_category = "GENERAL"

        # A. நகைக்கடன் எண் (Loan No) மூலம் தேடுதல்
        loan_chk = supabase.table("test_gold_loans").select("*, test_gold_loan_items(*)").ilike("loan_no", f"%{q_upper}%").limit(1).execute().data or []
        if loan_chk:
            matched_loan = loan_chk[0]
            record_category = "GOLD_LOAN"
            customer_id = matched_loan.get("customer_id")
            if matched_loan.get("visit_id"):
                v_r = supabase.table("test_customer_visits").select("*").eq("id", matched_loan["visit_id"]).execute().data
                if v_r:
                    visit = v_r[0]
        else:
            # B. நகை வாங்குதல் (GP), விற்பனை (GS), GSS, RD, SI எண் மூலம் தேடுதல்
            for tbl, col, cat in [
                ("test_gold_purchases", "gp_no", "GOLD_PURCHASE"),
                ("test_gold_sales", "gs_no", "GOLD_SALE"),
                ("test_customer_savings_accounts", "gss_no", "GSS"),
                ("test_customer_rd_accounts", "rd_no", "RD"),
                ("test_si_accounts", "si_no", "SI"),
            ]:
                try:
                    r_chk = supabase.table(tbl).select("*").ilike(col, f"%{q_upper}%").limit(1).execute().data or []
                    if r_chk:
                        extra_record = r_chk[0]
                        record_category = cat
                        customer_id = extra_record.get("customer_id")
                        if extra_record.get("visit_id"):
                            v_r = supabase.table("test_customer_visits").select("*").eq("id", extra_record["visit_id"]).execute().data
                            if v_r:
                                visit = v_r[0]
                        break
                except Exception:
                    continue

        # C. வருகை எண் (Visit ID) அல்லது மொபைல் எண் மூலம் தேடுதல்
        if not matched_loan and not extra_record:
            clean_num = q_upper.replace("#VIS-", "").replace("VIS-", "").strip()
            if clean_num.isdigit() and len(clean_num) < 10:
                v_r = supabase.table("test_customer_visits").select("*").eq("id", int(clean_num)).execute().data
                if v_r:
                    visit = v_r[0]
                    customer_id = visit.get("customer_id")
            if not visit:
                c_r = supabase.table("test_customers").select("*").or_(f"mobile.ilike.%{q}%,name.ilike.%{q}%").limit(1).execute().data
                if c_r:
                    customer = c_r[0]
                    customer_id = customer["id"]
                    v_last = supabase.table("test_customer_visits").select("*").eq("customer_id", customer_id).order("id", desc=True).limit(1).execute().data
                    if v_last:
                        visit = v_last[0]

        if not matched_loan and not extra_record and not visit and not customer:
            raise HTTPException(status_code=404, detail=f"'{query}' என்ற எண்ணில் எந்தப் பதிவும் கிடைக்கவில்லை.")

        # வாடிக்கையாளர் முழு KYC விவரம்
        if not customer and customer_id:
            c_res = supabase.table("test_customers").select("*").eq("id", customer_id).execute().data
            customer = c_res[0] if c_res else {}

        # வருகை கிடைக்கவில்லை எனில் வாடிக்கையாளரின் சமீபத்திய வருகை எடுத்தல்
        if not visit and customer_id:
            v_q = supabase.table("test_customer_visits").select("*").eq("customer_id", customer_id).ilike("actions_summary", f"%{q_upper}%").limit(1).execute().data
            if v_q:
                visit = v_q[0]

        # 2. கடன் தொடர்பான பாக்கெட் வரலாறு, வட்டி வரவுகள் & தள்ளுபடி விவரங்கள்
        packet_movements = []
        repayments = []
        rebates = []
        if matched_loan:
            lno = matched_loan["loan_no"]
            pkt_r = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute().data
            if pkt_r:
                matched_packet = pkt_r[0]
                mov_r = supabase.table("test_gold_packet_movements").select("*").eq("packet_id", matched_packet["id"]).order("id").execute().data or []
                for m in mov_r:
                    m["performed_by_name"] = s_map.get(m.get("performed_by"), "-")
                packet_movements = mov_r

            repayments = supabase.table("test_loan_repayments").select("*").eq("loan_id", matched_loan["id"]).order("id").execute().data or []
            reb_r = supabase.table("test_rebate_approvals").select("*").eq("loan_id", matched_loan["id"]).execute().data or []
            for rb in reb_r:
                rb["requested_by_name"] = s_map.get(rb.get("requested_by"), "-")
                rb["approved_by_name"] = s_map.get(rb.get("approved_by"), "-")
            rebates = reb_r

        # 3. தீர்வு (Settlement), OTP & வங்கிப் பரிமாற்ற விவரங்கள்
        settlement = {}
        denominations = {}
        otp_info = {}
        bank_transfers = []
        audit_docs = []
        incentive_entries = []

        if visit:
            vid = visit["id"]
            visit["branch_name"] = b_map.get(visit.get("branch_id"), f"கிளை #{visit.get('branch_id')}")

            if customer and customer.get("id"):
                s_res = supabase.table("test_transaction_settlements").select("*, test_cash_denominations(*)").eq("customer_id", customer.get("id")).eq("transaction_date", visit.get("transaction_date")).order("id", desc=True).limit(1).execute().data
                if s_res:
                    settlement = s_res[0]
                    if settlement.get("test_cash_denominations"):
                        denominations = settlement["test_cash_denominations"][0]
                    bt_r = supabase.table("test_bank_transfers").select("*").eq("settlement_id", settlement["id"]).execute().data or []
                    for bt in bt_r:
                        bt["approved_by_name"] = s_map.get(bt.get("approved_by"), "-")
                    bank_transfers = bt_r

                o_res = supabase.table("test_transaction_otps").select("*").eq("customer_id", customer.get("id")).order("id", desc=True).limit(1).execute().data
                if o_res:
                    otp_info = o_res[0]

            d_res = supabase.table("test_visit_audit_documents").select("*").eq("visit_id", vid).order("id").execute().data or []
            for d in d_res:
                d["uploaded_by_name"] = s_map.get(d.get("uploaded_by"), "-")
                d["audited_by_name"] = s_map.get(d.get("audited_by"), "-")
            audit_docs = d_res

        # இன்சென்டிவ் லெட்ஜரில் உள்ள வணிக ஆதார விவரம்
        ref_search = matched_loan["loan_no"] if matched_loan else (q_upper)
        inc_r = supabase.table("test_staff_incentive_ledger").select("*").ilike("ref_no", f"%{ref_search}%").execute().data or []
        for ir in inc_r:
            ir["staff_name"] = s_map.get(ir.get("staff_id"), "-")
        incentive_entries = inc_r

        return {
            "status": "success",
            "category": record_category,
            "customer": customer,
            "visit": visit,
            "loan": matched_loan,
            "extra_record": extra_record,
            "packet": matched_packet,
            "packet_movements": packet_movements,
            "repayments": repayments,
            "rebates": rebates,
            "settlement": settlement,
            "denominations": denominations,
            "otp_info": otp_info,
            "bank_transfers": bank_transfers,
            "audit_docs": audit_docs,
            "incentive_entries": incentive_entries
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"360° தேடல் பிழை: {str(e)}")

# ==============================================================================
# ⚡ பாக்கெட் ஒப்படைப்பு OTP விலக்கு (Packet Handover OTP Exemption APIs)
# ==============================================================================
@app.post("/api/packets/request-handover-otp-exempt")
def request_packet_handover_otp_exempt(data: dict):
    try:
        lno = str(data.get("loan_no") or "").strip()
        reason = str(data.get("reason") or "").strip()
        if not lno or not reason:
            raise HTTPException(status_code=400, detail="கடன் எண் மற்றும் காரணத்தை உள்ளிடவும்.")

        pkt_res = supabase.table("test_gold_packets").select("*").eq("loan_no", lno).execute()
        if not pkt_res.data:
            raise HTTPException(status_code=404, detail="பாக்கெட் கிடைக்கவில்லை.")
        pkt = pkt_res.data[0]

        if not pkt.get("is_loan_closed"):
            raise HTTPException(status_code=400, detail="❌ முதலில் கவுண்ட்டரில் நகைக்கடனை முழுமையாக முடிக்கவும்!")

        supabase.table("test_gold_packets").update({
            "handover_otp_exempt_status": "REQUESTED",
            "handover_otp_exempt_reason": reason,
            "updated_at": datetime.now(IST).isoformat()
        }).eq("id", pkt["id"]).execute()

        return {"status": "success", "message": "பாக்கெட் ஒப்படைப்பு OTP விலக்குக் கோரிக்கை தலைமையகத்திற்கு அனுப்பப்பட்டது!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hq/pending-packet-otp-exemptions")
def get_pending_packet_otp_exemptions():
    try:
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        c_map = {c["id"]: c for c in (cust_res.data or [])}
        br_res = supabase.table("test_branches").select("id, branch_name").execute()
        b_map = {b["id"]: b.get("branch_name") for b in (br_res.data or [])}

        res = supabase.table("test_gold_packets").select("*").eq("handover_otp_exempt_status", "REQUESTED").order("updated_at", desc=True).execute()
        list_data = res.data or []
        for p in list_data:
            c = c_map.get(p.get("customer_id"), {})
            p["customer_name"] = c.get("name", "-")
            p["customer_mobile"] = c.get("mobile", "-")
            p["branch_name"] = b_map.get(p.get("branch_id"), f"கிளை #{p.get('branch_id')}")
        return {"status": "success", "data": list_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-packet-otp-exemption")
def approve_packet_handover_otp_exemption(data: dict):
    try:
        lno = str(data.get("loan_no") or "").strip()
        action = str(data.get("action") or "APPROVE")
        new_st = "APPROVED" if action == "APPROVE" else "REJECTED"

        supabase.table("test_gold_packets").update({
            "handover_otp_exempt_status": new_st,
            "updated_at": datetime.now(IST).isoformat()
        }).eq("loan_no", lno).execute()

        msg = f"✅ பாக்கெட் ({lno}) ஒப்படைப்பு OTP விலக்கு அனுமதிக்கப்பட்டது!" if new_st == "APPROVED" else "❌ OTP விலக்கு நிராகரிக்கப்பட்டது."
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# 🔔 கவுண்டர் முகப்பு: தலைமையக ஒப்புதல் நிலுவை & நிராகரிக்கப்பட்டவை (Counter Status Bar)
# ==============================================================================
@app.get("/api/counter/hq-approval-status")
def get_counter_hq_approval_status(branch_id: int = Query(...), date_str: str = Query(...)):
    try:
        cust_res = supabase.table("test_customers").select("id, name").execute().data or []
        c_map = {c["id"]: c.get("name", "வாடிக்கையாளர்") for c in cust_res}

        pending_list = []
        rejected_list = []

        # 1. வருகைகள் (Visits)
        v_res = supabase.table("test_customer_visits").select("id, customer_id, status, net_amount, actions_summary, transaction_date").eq("branch_id", branch_id).eq("transaction_date", date_str).in_("status", ["PENDING_HQ", "REJECTED"]).order("id", desc=True).execute().data or []
        for v in v_res:
            item = {
                "type": "வருகை",
                "title": f"#VIS-{v['id']} | {c_map.get(v.get('customer_id'), '-')}",
                "detail": f"{v.get('actions_summary') or '-'} (₹{float(v.get('net_amount') or 0):,.0f})"
            }
            if v["status"] == "PENDING_HQ":
                pending_list.append(item)
            else:
                rejected_list.append(item)

        # 2. கிளை செலவுகள் (Expenses)
        e_res = supabase.table("test_branch_expenses").select("id, category, amount, reason, status, transaction_date").eq("branch_id", branch_id).eq("transaction_date", date_str).in_("status", ["PENDING", "REJECTED"]).order("id", desc=True).execute().data or []
        for e in e_res:
            item = {
                "type": "செலவு",
                "title": f"செலவு: {e.get('category', '-')}",
                "detail": f"{e.get('reason') or '-'} (₹{float(e.get('amount') or 0):,.0f})"
            }
            if e["status"] == "PENDING":
                pending_list.append(item)
            else:
                rejected_list.append(item)

        # 3. உள்-பணப் பரிமாற்றம் (Treasury)
        t_res = supabase.table("test_treasury_transfers").select("id, transfer_type, amount, carrier_person, status, transaction_date").eq("branch_id", branch_id).eq("transaction_date", date_str).in_("status", ["PENDING", "REJECTED"]).order("id", desc=True).execute().data or []
        for t in t_res:
            item = {
                "type": "பணப் பரிமாற்றம்",
                "title": f"{t.get('transfer_type', '-')}",
                "detail": f"{t.get('carrier_person') or '-'} (₹{float(t.get('amount') or 0):,.0f})"
            }
            if t["status"] == "PENDING":
                pending_list.append(item)
            else:
                rejected_list.append(item)

        return {"status": "success", "pending": pending_list, "rejected": rejected_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
