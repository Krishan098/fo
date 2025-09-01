from app.services.process import *
from pypdf import PdfReader
import io

processing_status: dict[str, dict[str, Any]] = {}
processing_results: dict[str, dict[str, Any]] = {}
from tqdm import tqdm
import time

def process_contract(contract_id: str, file_bytes: bytes, filename: str):
    try:
        steps = [
            "reading_pdf",
            "extracting_contract_id",
            "party_extraction",
            "account_info_extraction",
            "financial_extraction",
            "payment_structure_extraction",
            "revenue_classification_extraction",
            "sla_extract",
            "saving_results"
        ]

       
        for i, step in enumerate(tqdm(steps, desc=f"Processing {contract_id}")):
            processing_status[contract_id] = {
                "state": "processing",
                "progress": int(((i + 1) / len(steps)) * 100),
                "current_step": step,
            }

            if step == "reading_pdf":
                reader = PdfReader(io.BytesIO(file_bytes))
                text = "\n".join([p.extract_text() or "" for p in reader.pages])

            elif step == "extracting_contract_id":
                b = io.BytesIO(file_bytes)
                extracted_id = extractContractId(b)
        
            elif step == "party_extraction":
                extracted_party=extractParty(text)
            
            elif step=="account_info_extraction":
                extracted_acc_info=extractAccInformation(text)

            elif step == "financial_extraction":
                extracted_financial_details=extract_financial_details(text)
            
            elif step=='payment_structure_extraction':
                extracted_payment_struct=extract_payment_structure(text)
            elif step=='revenue_classification_extraction':
                extracted_revenue_classification=extract_revenue_classification(text)
            elif step=='sla_extract':
                extracted_sla=extract_sla(text)
                
            elif step=='saving_results':
                results = {
                    "filename": filename,
                    "contract_id": extracted_id.strip() if extracted_id else None,
                    "size_bytes": len(file_bytes),
                    "party": extracted_party,
                    "account_info": extracted_acc_info,
                    "financial_details": extracted_financial_details,
                    "payment_structure": extracted_payment_struct,
                    "revenue_classification": extracted_revenue_classification,
                    "sla": extracted_sla,
                }
                processing_results[contract_id] = results

            time.sleep(0.5)  

        processing_status[contract_id] = {"state": "completed", "progress": 100}

    except Exception as e:
        processing_status[contract_id] = {
            "state": "failed",
            "progress": 100,
            "error": str(e),
        }
