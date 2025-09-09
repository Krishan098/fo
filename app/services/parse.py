from app.services.process import *
from pypdf import PdfReader
import io
from typing import Any
import time

# Global dictionaries that will be imported by main.py
processing_status: dict[str, dict[str, Any]] = {}
processing_results: dict[str, dict[str, Any]] = {}

def process_contract(contract_id: str, file_bytes: bytes, filename: str):
    try:
        # Simplified steps since we're using Cohere for extraction
        steps = [
            "reading_pdf",
            "extracting_contract_id", 
            "extracting_contract_data",
            "calculating_scores",
            "saving_results"
        ]

        for i, step in enumerate(steps):
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
                
            elif step == "extracting_contract_data":
                # Use the comprehensive extraction function
                all_data = extract_all_contract_data(text)
                
                # Extract individual components
                extracted_party = all_data.get("party", {})
                extracted_acc_info = all_data.get("account_info", {})
                extracted_financial_details = all_data.get("financial_details", {})
                extracted_payment_struct = all_data.get("payment_structure", {})
                extracted_revenue_classification = all_data.get("revenue_classification", {})
                extracted_sla = all_data.get("sla", {})
                
            elif step == "calculating_scores":
                # Calculate confidence scores and identify gaps
                extracted_data = {
                    "party": extracted_party,
                    "account_info": extracted_acc_info,
                    "financial_details": extracted_financial_details,
                    "payment_structure": extracted_payment_struct,
                    "revenue_classification": extracted_revenue_classification,
                    "sla": extracted_sla,
                }
                
                confidence_scores = calculate_confidence_score(extracted_data)
                gaps = identify_gaps(extracted_data)
                
            elif step == "saving_results":
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
                    "confidence_scores": confidence_scores,
                    "gaps": gaps,
                    "processing_timestamp": time.time()
                }
                processing_results[contract_id] = results

            # Add a small delay to simulate processing time
            time.sleep(0.8)  

        processing_status[contract_id] = {"state": "completed", "progress": 100}

    except Exception as e:
        processing_status[contract_id] = {
            "state": "failed",
            "progress": 100,
            "error": str(e),
        }
        print(f"Error processing contract {contract_id}: {str(e)}")  # Add logging for debugging