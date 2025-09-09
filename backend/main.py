# from typing import Annotated
# from app.services.process import extractContractId
# from app.services.parse import process_contract,processing_results,processing_status
# from fastapi import FastAPI, UploadFile,File,HTTPException,BackgroundTasks
# from fastapi.responses import HTMLResponse
# import io
# from typing import Any
# import uuid
# app = FastAPI()

# @app.post("/contracts/upload/")
# async def create_upload_contracts(background_tasks:BackgroundTasks,contracts: Annotated[list[UploadFile]|None,File(description="Multiple contracts as UploadContracts")]):
#     contract_ids=[]
#     if not contracts:
#         return {"message":"No file uploaded"}
#     else:
#         for i in contracts:
#             if i.content_type!="application/pdf":
#                 raise HTTPException(status_code=422,detail="Only accepts PDFs for contracts")
#             bytess=await i.read()
#             buffer=io.BytesIO(bytess)
#             contract_id = extractContractId(buffer)
#             contract_ids.append(contract_id)
#             processing_status[contract_id] = {"state": "pending", "progress": 0}
#             background_tasks.add_task(process_contract, contract_id,bytess,i.filename)

#     return {"contract_ids": contract_ids,"filename":i.filename}


# @app.get("/contracts/{contract_id}/status")
# async def get_contract_status(contract_id: str):
#     if contract_id not in processing_status:
#         raise HTTPException(status_code=404, detail="Contract ID not found")

#     status = processing_status[contract_id]
#     result = processing_results.get(contract_id)
#     return {"status": status, "results": result if status["state"] == "completed" else None}
# @app.get("/")
# async def main():
#     content = """
# <body>
# <form action="/contracts/upload/" enctype="multipart/form-data" method="post">
# <input name="contracts" type="file" multiple>
# <input type="submit">
# </form>
# </body>
#     """
#     return HTMLResponse(content=content)

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import os
import json
import asyncio
from datetime import datetime
import pypdf
import io
from enum import Enum
import cohere
from pathlib import Path

# Initialize FastAPI app
app = FastAPI(title="Contract Intelligence Parser", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Cohere client
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "your-cohere-api-key")
co = cohere.ClientV2(api_key=COHERE_API_KEY)

# Enums
class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class RevenueType(str, Enum):
    RECURRING = "recurring"
    ONE_TIME = "one_time"
    BOTH = "both"

# Pydantic models
class PartyInfo(BaseModel):
    name: str
    legal_entity: Optional[str] = None
    registration_details: Optional[str] = None
    signatories: List[str] = []
    roles: List[str] = []

class AccountInfo(BaseModel):
    billing_details: Optional[str] = None
    account_numbers: List[str] = []
    contact_info: Optional[str] = None

class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None

class FinancialDetails(BaseModel):
    line_items: List[LineItem] = []
    total_value: Optional[float] = None
    currency: Optional[str] = None
    tax_info: Optional[str] = None
    additional_fees: List[str] = []

class PaymentStructure(BaseModel):
    payment_terms: Optional[str] = None
    payment_schedule: List[str] = []
    due_dates: List[str] = []
    payment_methods: List[str] = []
    banking_details: Optional[str] = None

class RevenueClassification(BaseModel):
    revenue_type: Optional[RevenueType] = None
    billing_cycle: Optional[str] = None
    renewal_terms: Optional[str] = None
    auto_renewal: Optional[bool] = None

class ServiceLevelAgreement(BaseModel):
    performance_metrics: List[str] = []
    penalty_clauses: List[str] = []
    support_terms: List[str] = []
    maintenance_terms: List[str] = []

class ContractScore(BaseModel):
    total_score: float
    financial_completeness: float
    party_identification: float
    payment_terms_clarity: float
    sla_definition: float
    contact_information: float
    missing_fields: List[str] = []

class ContractData(BaseModel):
    contract_id: str
    filename: str
    upload_date: datetime
    status: ProcessingStatus
    progress: float = 0.0
    error_message: Optional[str] = None
    parties: List[PartyInfo] = []
    account_info: Optional[AccountInfo] = None
    financial_details: Optional[FinancialDetails] = None
    payment_structure: Optional[PaymentStructure] = None
    revenue_classification: Optional[RevenueClassification] = None
    sla: Optional[ServiceLevelAgreement] = None
    score: Optional[ContractScore] = None

# In-memory storage (replace with MongoDB in production)
contracts_db: Dict[str, ContractData] = {}
file_storage: Dict[str, bytes] = {}

# Ensure upload directory exists
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

class ContractProcessor:
    def __init__(self):
        self.co = co

    async def extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF file."""
        try:
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error extracting PDF text: {str(e)}")

    async def parse_contract_with_cohere(self, text: str) -> Dict[str, Any]:
        """Use Cohere to parse contract data."""
        prompt = f"""
        Analyze the following contract text and extract structured information. Return your response as a valid JSON object with the following structure:

        {{
            "parties": [
                {{
                    "name": "Party name",
                    "legal_entity": "Legal entity name",
                    "registration_details": "Registration details",
                    "signatories": ["Signatory names"],
                    "roles": ["Roles"]
                }}
            ],
            "account_info": {{
                "billing_details": "Billing information",
                "account_numbers": ["Account numbers"],
                "contact_info": "Contact information"
            }},
            "financial_details": {{
                "line_items": [
                    {{
                        "description": "Item description",
                        "quantity": 1.0,
                        "unit_price": 100.0,
                        "total_price": 100.0
                    }}
                ],
                "total_value": 1000.0,
                "currency": "USD",
                "tax_info": "Tax information",
                "additional_fees": ["Fee descriptions"]
            }},
            "payment_structure": {{
                "payment_terms": "Payment terms",
                "payment_schedule": ["Payment schedule"],
                "due_dates": ["Due dates"],
                "payment_methods": ["Payment methods"],
                "banking_details": "Banking details"
            }},
            "revenue_classification": {{
                "revenue_type": "recurring" | "one_time" | "both",
                "billing_cycle": "Billing cycle",
                "renewal_terms": "Renewal terms",
                "auto_renewal": true | false
            }},
            "sla": {{
                "performance_metrics": ["Performance metrics"],
                "penalty_clauses": ["Penalty clauses"],
                "support_terms": ["Support terms"],
                "maintenance_terms": ["Maintenance terms"]
            }}
        }}

        Contract text:
        {text}

        Extract all available information and return only the JSON response. If information is not available, use null values or empty arrays as appropriate.
        """

        try:
            response = self.co.chat(
                model="command-r-plus",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000
            )
            
            # Extract JSON from response
            response_text = response.message.content[0].text
            
            # Try to parse the JSON response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            json_str = response_text[start_idx:end_idx]
            
            return json.loads(json_str)
        except Exception as e:
            print(f"Error with Cohere API: {str(e)}")
            # Return empty structure if API fails
            return {
                "parties": [],
                "account_info": {},
                "financial_details": {},
                "payment_structure": {},
                "revenue_classification": {},
                "sla": {}
            }

    def calculate_score(self, contract_data: Dict[str, Any]) -> ContractScore:
        """Calculate contract completeness score."""
        scores = {
            "financial_completeness": 0.0,
            "party_identification": 0.0,
            "payment_terms_clarity": 0.0,
            "sla_definition": 0.0,
            "contact_information": 0.0
        }
        missing_fields = []

        # Financial completeness (30 points)
        financial = contract_data.get("financial_details", {})
        if financial.get("total_value"):
            scores["financial_completeness"] += 15
        if financial.get("currency"):
            scores["financial_completeness"] += 5
        if financial.get("line_items"):
            scores["financial_completeness"] += 10
        else:
            missing_fields.append("Line items")

        # Party identification (25 points)
        parties = contract_data.get("parties", [])
        if parties:
            scores["party_identification"] += 15
            if any(p.get("legal_entity") for p in parties):
                scores["party_identification"] += 5
            if any(p.get("signatories") for p in parties):
                scores["party_identification"] += 5
        else:
            missing_fields.append("Contract parties")

        # Payment terms clarity (20 points)
        payment = contract_data.get("payment_structure", {})
        if payment.get("payment_terms"):
            scores["payment_terms_clarity"] += 10
        if payment.get("payment_methods"):
            scores["payment_terms_clarity"] += 5
        if payment.get("due_dates"):
            scores["payment_terms_clarity"] += 5
        else:
            missing_fields.append("Payment due dates")

        # SLA definition (15 points)
        sla = contract_data.get("sla", {})
        if sla.get("performance_metrics"):
            scores["sla_definition"] += 8
        if sla.get("support_terms"):
            scores["sla_definition"] += 7
        else:
            missing_fields.append("Service level agreements")

        # Contact information (10 points)
        account_info = contract_data.get("account_info", {})
        if account_info.get("contact_info"):
            scores["contact_information"] += 5
        if account_info.get("billing_details"):
            scores["contact_information"] += 5
        else:
            missing_fields.append("Contact information")

        total_score = sum(scores.values())

        return ContractScore(
            total_score=total_score,
            financial_completeness=scores["financial_completeness"],
            party_identification=scores["party_identification"],
            payment_terms_clarity=scores["payment_terms_clarity"],
            sla_definition=scores["sla_definition"],
            contact_information=scores["contact_information"],
            missing_fields=missing_fields
        )

    async def process_contract(self, contract_id: str, file_content: bytes, filename: str):
        """Process contract asynchronously."""
        try:
            # Update status to processing
            contracts_db[contract_id].status = ProcessingStatus.PROCESSING
            contracts_db[contract_id].progress = 10.0

            # Extract text from PDF
            text = await self.extract_text_from_pdf(file_content)
            contracts_db[contract_id].progress = 30.0

            # Parse with Cohere
            parsed_data = await self.parse_contract_with_cohere(text)
            contracts_db[contract_id].progress = 70.0

            # Calculate score
            score = self.calculate_score(parsed_data)
            contracts_db[contract_id].progress = 90.0

            # Update contract data
            contract = contracts_db[contract_id]
            
            # Map parsed data to contract structure
            if parsed_data.get("parties"):
                contract.parties = [PartyInfo(**party) for party in parsed_data["parties"]]
            
            if parsed_data.get("account_info"):
                contract.account_info = AccountInfo(**parsed_data["account_info"])
            
            if parsed_data.get("financial_details"):
                financial = parsed_data["financial_details"]
                line_items = []
                if financial.get("line_items"):
                    line_items = [LineItem(**item) for item in financial["line_items"]]
                contract.financial_details = FinancialDetails(
                    line_items=line_items,
                    total_value=financial.get("total_value"),
                    currency=financial.get("currency"),
                    tax_info=financial.get("tax_info"),
                    additional_fees=financial.get("additional_fees", [])
                )
            
            if parsed_data.get("payment_structure"):
                contract.payment_structure = PaymentStructure(**parsed_data["payment_structure"])
            
            if parsed_data.get("revenue_classification"):
                rev_class = parsed_data["revenue_classification"]
                contract.revenue_classification = RevenueClassification(
                    revenue_type=rev_class.get("revenue_type"),
                    billing_cycle=rev_class.get("billing_cycle"),
                    renewal_terms=rev_class.get("renewal_terms"),
                    auto_renewal=rev_class.get("auto_renewal")
                )
            
            if parsed_data.get("sla"):
                contract.sla = ServiceLevelAgreement(**parsed_data["sla"])
            
            contract.score = score
            contract.status = ProcessingStatus.COMPLETED
            contract.progress = 100.0

        except Exception as e:
            print(f"Error processing contract {contract_id}: {str(e)}")
            contracts_db[contract_id].status = ProcessingStatus.FAILED
            contracts_db[contract_id].error_message = str(e)
            contracts_db[contract_id].progress = 0.0

# Initialize processor
processor = ContractProcessor()

# API Endpoints

@app.post("/contracts/upload")
async def upload_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload a contract file for processing."""
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Validate file size (50MB limit)
    file_content = await file.read()
    if len(file_content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")
    
    # Generate contract ID
    contract_id = str(uuid.uuid4())
    
    # Store file content
    file_storage[contract_id] = file_content
    
    # Create contract record
    contract = ContractData(
        contract_id=contract_id,
        filename=file.filename,
        upload_date=datetime.now(),
        status=ProcessingStatus.PENDING
    )
    contracts_db[contract_id] = contract
    
    # Start background processing
    background_tasks.add_task(processor.process_contract, contract_id, file_content, file.filename)
    
    return {"contract_id": contract_id, "status": "uploaded", "message": "Contract processing initiated"}

@app.get("/contracts/{contract_id}/status")
async def get_contract_status(contract_id: str):
    """Get contract processing status."""
    
    if contract_id not in contracts_db:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    contract = contracts_db[contract_id]
    
    return {
        "contract_id": contract_id,
        "status": contract.status,
        "progress": contract.progress,
        "error_message": contract.error_message
    }

@app.get("/contracts/{contract_id}")
async def get_contract_data(contract_id: str):
    """Get parsed contract data."""
    
    if contract_id not in contracts_db:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    contract = contracts_db[contract_id]
    
    if contract.status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Contract processing not completed. Current status: {contract.status}"
        )
    
    return contract

@app.get("/contracts")
async def get_contracts(
    status: Optional[ProcessingStatus] = Query(None, description="Filter by status"),
    limit: int = Query(10, description="Number of contracts per page"),
    offset: int = Query(0, description="Offset for pagination"),
    sort_by: str = Query("upload_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)")
):
    """Get paginated list of contracts with filtering."""
    
    contracts_list = list(contracts_db.values())
    
    # Filter by status if provided
    if status:
        contracts_list = [c for c in contracts_list if c.status == status]
    
    # Sort contracts
    reverse = sort_order.lower() == "desc"
    if sort_by == "upload_date":
        contracts_list.sort(key=lambda x: x.upload_date, reverse=reverse)
    elif sort_by == "score" and hasattr(contracts_list[0], 'score') and contracts_list[0].score:
        contracts_list.sort(key=lambda x: x.score.total_score if x.score else 0, reverse=reverse)
    elif sort_by == "filename":
        contracts_list.sort(key=lambda x: x.filename, reverse=reverse)
    
    # Paginate
    total = len(contracts_list)
    contracts_page = contracts_list[offset:offset + limit]
    
    return {
        "contracts": contracts_page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total
    }

@app.get("/contracts/{contract_id}/download")
async def download_contract(contract_id: str):
    """Download original contract file."""
    
    if contract_id not in contracts_db:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if contract_id not in file_storage:
        raise HTTPException(status_code=404, detail="Contract file not found")
    
    contract = contracts_db[contract_id]
    file_content = file_storage[contract_id]
    
    # Save file temporarily for download
    temp_path = UPLOAD_DIR / f"{contract_id}_{contract.filename}"
    with open(temp_path, "wb") as f:
        f.write(file_content)
    
    return FileResponse(
        path=temp_path,
        filename=contract.filename,
        media_type="application/pdf"
    )

@app.delete("/contracts/{contract_id}")
async def delete_contract(contract_id: str):
    """Delete a contract and its associated data."""
    
    if contract_id not in contracts_db:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Clean up data
    del contracts_db[contract_id]
    if contract_id in file_storage:
        del file_storage[contract_id]
    
    # Clean up temporary files
    temp_path = UPLOAD_DIR / f"{contract_id}_*"
    for file_path in UPLOAD_DIR.glob(f"{contract_id}_*"):
        file_path.unlink(missing_ok=True)
    
    return {"message": "Contract deleted successfully"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Contract Intelligence Parser API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /contracts/upload",
            "status": "GET /contracts/{contract_id}/status",
            "data": "GET /contracts/{contract_id}",
            "list": "GET /contracts",
            "download": "GET /contracts/{contract_id}/download"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)