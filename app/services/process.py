from pypdf import PdfReader
import io
import re
import json
import logging

from typing import Any
from dotenv import load_dotenv
load_dotenv()
import cohere
import os
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
co = cohere.ClientV2(os.getenv("COHERE_API_KEY"))



def extractContractId(file: io.BytesIO) -> str:
    """Extract contract ID from PDF"""
    file.seek(0)
    reader = PdfReader(file)
    text = reader.pages[0].extract_text() or ""
    
    # Multiple patterns for contract ID
    patterns = [
        r"Contract\s*(?:ID|Number|#)\s*:?\s*([A-Za-z0-9\-_]+)",
        r"Agreement\s*(?:ID|Number|#)\s*:?\s*([A-Za-z0-9\-_]+)",
        r"SSA[-_](\d{4}[-_]\d{4})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return f"UNKNOWN_{hash(text[:100]) % 10000}"

def extract_with_cohere(text: str, extraction_type: str) -> dict[str, Any]:
    """Generic function to extract information using Cohere"""
    if not co:
        logger.error("Cohere client not initialized. Please set COHERE_API_KEY.")
        return {}
    
    prompts = {
        "party": """
        Extract party information from this contract text. Return a JSON object with:
        {
            "service_provider": {
                "name": "company name",
                "location": "city, state",
                "contact": {
                    "phone": "phone number",
                    "email": "email address"
                }
            },
            "customer": {
                "name": "customer company name", 
                "location": "city, state",
                "contact": {
                    "phone": "phone number",
                    "email": "email address"
                }
            },
            "authorized_reps": ["list of authorized representative names"]
        }
        
        Contract text:
        """,
        
        "account_info": """
        Extract account and billing information from this contract text. Return a JSON object with:
        {
            "account_number": "customer account number",
            "billing_contact": {
                "name": "billing contact person name",
                "email": "billing email address", 
                "phone": "billing phone number"
            },
            "banking_information": {
                "bank_name": "bank name",
                "account_number": "bank account number",
                "routing_number": "routing number"
            }
        }
        
        Contract text:
        """,
        
        "financial": """
        Extract financial information from this contract text. Return a JSON object with:
        {
            "total_value": 242500.00,
            "currency": "USD",
            "breakdown": {
                "monthly_recurring": 19000.00,
                "one_time_setup": 14500.00,
                "annual_recurring": 228000.00
            },
            "line_items": [
                {"description": "Cloud Infrastructure", "amount": 7500.00, "frequency": "monthly"},
                {"description": "Software Licenses", "amount": 9000.00, "frequency": "monthly"}
            ]
        }
        
        Contract text:
        """,
        
        "payment_structure": """
        Extract payment terms and structure from this contract text. Return a JSON object with:
        {
            "terms": "Net 30",
            "method": "ACH transfer", 
            "due_date": "30th of each month",
            "frequency": "monthly",
            "late_fees": "1.5% monthly interest"
        }
        
        Contract text:
        """,
        
        "revenue_classification": """
        Analyze the revenue model from this contract text. Return a JSON object with:
        {
            "recurring": true,
            "one_time": true,
            "auto_renewal": true,
            "subscription": false,
            "usage_based": false,
            "contract_term": "24 months"
        }
        
        Contract text:
        """,
        
        "sla": """
        Extract service level agreement details from this contract text. Return a JSON object with:
        {
            "availability": "99.9% uptime",
            "response_times": {
                "critical": "1 hour",
                "high": "4 hours", 
                "medium": "8 hours",
                "low": "24 hours"
            },
            "performance_metrics": {
                "response_time": "< 2 seconds",
                "backup_success_rate": "99.5%"
            },
            "service_credits": [
                "5% monthly fee credit for each 0.1% below 99.9% availability",
                "$500 credit for each SLA response time violation"
            ],
            "support_hours": "8x5"
        }
        
        Contract text:
        """
    }
    
    try:
        prompt = prompts.get(extraction_type, "")
        if not prompt:
            logger.error(f"Unknown extraction type: {extraction_type}")
            return {}
        
        full_prompt = prompt + text + "\n\nReturn only valid JSON, no additional text:"
        
        response = co.generate(
            model='command-r-plus',
            prompt=full_prompt,
            max_tokens=1000,
            temperature=0.1
        )
        
        # Extract JSON from response
        response_text = response.generations[0].text.strip()
        
        # Clean response to ensure it's valid JSON
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '')
        
        # Try to parse JSON
        try:
            result = json.loads(response_text)
            logger.info(f"Successfully extracted {extraction_type}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for {extraction_type}: {e}")
            logger.error(f"Response was: {response_text}")
            return {}
            
    except Exception as e:
        logger.error(f"Cohere API error for {extraction_type}: {e}")
        return {}

def extractParty(text: str) -> dict[str, Any]:
    """Extract party information using Cohere"""
    return extract_with_cohere(text, "party")

def extractAccInformation(text: str) -> dict[str, Any]:
    """Extract account information using Cohere"""
    return extract_with_cohere(text, "account_info")

def extract_financial_details(text: str) -> dict[str, Any]:
    """Extract financial details using Cohere"""
    return extract_with_cohere(text, "financial")

def extract_payment_structure(text: str) -> dict[str, Any]:
    """Extract payment structure using Cohere"""
    return extract_with_cohere(text, "payment_structure")

def extract_revenue_classification(text: str) -> dict[str, Any]:
    """Extract revenue classification using Cohere"""
    return extract_with_cohere(text, "revenue_classification")

def extract_sla(text: str) -> dict[str, Any]:
    """Extract SLA information using Cohere"""
    return extract_with_cohere(text, "sla")

def calculate_confidence_score(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate confidence scores for extracted data"""
    scores = {
        "overall": 0,
        "party_identification": 0,
        "financial_completeness": 0,
        "payment_terms": 0,
        "sla_definition": 0,
        "contact_information": 0
    }
    
    # Party identification scoring (25 points)
    party_score = 0
    party_data = extracted_data.get("party", {})
    if party_data.get("service_provider", {}).get("name"):
        party_score += 12.5
    if party_data.get("customer", {}).get("name"):
        party_score += 12.5
    scores["party_identification"] = party_score
    
    # Financial completeness scoring (30 points)
    financial_score = 0
    financial_data = extracted_data.get("financial_details", {})
    if financial_data.get("total_value"):
        financial_score += 15
    if financial_data.get("line_items"):
        financial_score += 10
    if financial_data.get("currency"):
        financial_score += 5
    scores["financial_completeness"] = financial_score
    
    # Payment terms scoring (20 points)
    payment_score = 0
    payment_data = extracted_data.get("payment_structure", {})
    if payment_data.get("terms"):
        payment_score += 8
    if payment_data.get("method"):
        payment_score += 6
    if payment_data.get("due_date"):
        payment_score += 6
    scores["payment_terms"] = payment_score
    
    # SLA definition scoring (15 points)
    sla_score = 0
    sla_data = extracted_data.get("sla", {})
    if sla_data.get("availability"):
        sla_score += 7
    if sla_data.get("response_times"):
        sla_score += 8
    scores["sla_definition"] = sla_score
    
    # Contact information scoring (10 points)
    contact_score = 0
    account_data = extracted_data.get("account_info", {})
    if account_data.get("billing_contact", {}).get("email"):
        contact_score += 5
    if account_data.get("billing_contact", {}).get("phone"):
        contact_score += 3
    if account_data.get("account_number"):
        contact_score += 2
    scores["contact_information"] = contact_score
    
    # Calculate overall score
    scores["overall"] = sum(scores.values()) - scores["overall"]  # Exclude overall from sum
    
    return scores

def identify_gaps(extracted_data: dict[str, Any]) -> list[str]:
    """Identify missing critical information"""
    gaps = []
    
    # Check party information
    party_data = extracted_data.get("party", {})
    if not party_data.get("service_provider", {}).get("name"):
        gaps.append("Service provider name not identified")
    if not party_data.get("customer", {}).get("name"):
        gaps.append("Customer name not identified")
    
    # Check financial details
    financial_data = extracted_data.get("financial_details", {})
    if not financial_data.get("total_value"):
        gaps.append("Total contract value not found")
    
    # Check payment structure
    payment_data = extracted_data.get("payment_structure", {})
    if not payment_data.get("terms"):
        gaps.append("Payment terms not defined")
    if not payment_data.get("method"):
        gaps.append("Payment method not specified")
    
    # Check SLA
    sla_data = extracted_data.get("sla", {})
    if not sla_data.get("availability"):
        gaps.append("Service availability target not defined")
    if not sla_data.get("response_times"):
        gaps.append("Support response times not specified")
    
    # Check contact information
    account_data = extracted_data.get("account_info", {})
    if not account_data.get("billing_contact", {}).get("email"):
        gaps.append("Billing contact email not found")
    
    return gaps

def extract_all_contract_data(text: str) -> dict[str, Any]:
    """Extract all contract data in a single Cohere call for efficiency"""
    if not co:
        logger.error("Cohere client not initialized. Please set COHERE_API_KEY.")
        return {}
    
    comprehensive_prompt = f"""
    You are a contract intelligence system. Extract all relevant information from this contract text and return it as a structured JSON object.

    Required JSON structure:
    {{
        "party": {{
            "service_provider": {{
                "name": "company name",
                "location": "city, state", 
                "contact": {{"phone": "phone", "email": "email"}}
            }},
            "customer": {{
                "name": "customer company name",
                "location": "city, state",
                "contact": {{"phone": "phone", "email": "email"}}
            }},
            "authorized_reps": ["rep1", "rep2"]
        }},
        "account_info": {{
            "account_number": "account number",
            "billing_contact": {{
                "name": "billing person name",
                "email": "billing email",
                "phone": "billing phone"
            }},
            "banking_information": {{
                "bank_name": "bank name",
                "account_number": "bank account",
                "routing_number": "routing number"
            }}
        }},
        "financial_details": {{
            "total_value": 242500.00,
            "currency": "USD",
            "breakdown": {{
                "monthly_recurring": 19000.00,
                "one_time_setup": 14500.00,
                "annual_recurring": 228000.00
            }},
            "line_items": [
                {{"description": "service description", "amount": 1000.00, "frequency": "monthly"}}
            ]
        }},
        "payment_structure": {{
            "terms": "Net 30",
            "method": "ACH transfer",
            "due_date": "30th of each month", 
            "frequency": "monthly",
            "late_fees": "1.5% monthly interest"
        }},
        "revenue_classification": {{
            "recurring": true,
            "one_time": true,
            "auto_renewal": true,
            "subscription": false,
            "usage_based": false,
            "contract_term": "24 months"
        }},
        "sla": {{
            "availability": "99.9% uptime",
            "response_times": {{
                "critical": "1 hour",
                "high": "4 hours",
                "medium": "8 hours", 
                "low": "24 hours"
            }},
            "performance_metrics": {{
                "response_time": "< 2 seconds",
                "backup_success_rate": "99.5%"
            }},
            "service_credits": [
                "5% monthly fee credit for each 0.1% below 99.9% availability"
            ],
            "support_hours": "8x5"
        }}
    }}

    Extract all information accurately. Use null for missing values. Return only valid JSON.

    Contract text:
    {text}

    JSON Response:
    """
    
    try:
        response = co.generate(
            model='command-r-plus',
            prompt=comprehensive_prompt,
            max_tokens=2000,
            temperature=0.1
        )
        
        response_text = response.generations[0].text.strip()
        
        # Clean response
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '')
        
        # Parse JSON
        result = json.loads(response_text)
        logger.info("Successfully extracted all contract data with Cohere")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response was: {response_text}")
        return {}
    except Exception as e:
        logger.error(f"Cohere API error: {e}")
        return {}

# Individual extraction functions for backward compatibility
def extractParty(text: str) -> dict[str, Any]:
    """Extract party information using Cohere"""
    full_data = extract_all_contract_data(text)
    return full_data.get("party", {
        "service_provider": {"name": None, "location": None, "contact": {}},
        "customer": {"name": None, "location": None, "contact": {}},
        "authorized_reps": []
    })

def extractAccInformation(text: str) -> dict[str, Any]:
    """Extract account information using Cohere"""
    full_data = extract_all_contract_data(text)
    return full_data.get("account_info", {
        "account_number": None,
        "billing_contact": {"name": None, "email": None, "phone": None},
        "banking_information": {}
    })

def extract_financial_details(text: str) -> dict[str, Any]:
    """Extract financial details using Cohere"""
    full_data = extract_all_contract_data(text)
    return full_data.get("financial_details", {
        "total_value": None,
        "currency": "USD",
        "breakdown": {},
        "line_items": []
    })

def extract_payment_structure(text: str) -> dict[str, Any]:
    """Extract payment structure using Cohere"""
    full_data = extract_all_contract_data(text)
    return full_data.get("payment_structure", {
        "terms": None,
        "method": None,
        "due_date": None,
        "frequency": None,
        "late_fees": None
    })

def extract_revenue_classification(text: str) -> dict[str, Any]:
    """Extract revenue classification using Cohere"""
    full_data = extract_all_contract_data(text)
    return full_data.get("revenue_classification", {
        "recurring": False,
        "one_time": False,
        "auto_renewal": False,
        "subscription": False,
        "usage_based": False,
        "contract_term": None
    })

def extract_sla(text: str) -> dict[str, Any]:
    """Extract SLA information using Cohere"""
    full_data = extract_all_contract_data(text)
    return full_data.get("sla", {
        "availability": None,
        "response_times": {},
        "performance_metrics": {},
        "service_credits": [],
        "support_hours": None
    })

def calculate_confidence_score(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate confidence scores for extracted data"""
    scores = {
        "overall": 0,
        "party_identification": 0,
        "financial_completeness": 0,
        "payment_terms": 0,
        "sla_definition": 0,
        "contact_information": 0
    }
    
    # Party identification scoring (25 points)
    party_score = 0
    party_data = extracted_data.get("party", {})
    if party_data.get("service_provider", {}).get("name"):
        party_score += 12.5
    if party_data.get("customer", {}).get("name"):
        party_score += 12.5
    scores["party_identification"] = party_score
    
    # Financial completeness scoring (30 points)
    financial_score = 0
    financial_data = extracted_data.get("financial_details", {})
    if financial_data.get("total_value"):
        financial_score += 15
    if financial_data.get("breakdown", {}).get("monthly_recurring"):
        financial_score += 10
    if financial_data.get("currency"):
        financial_score += 5
    scores["financial_completeness"] = financial_score
    
    # Payment terms scoring (20 points)
    payment_score = 0
    payment_data = extracted_data.get("payment_structure", {})
    if payment_data.get("terms"):
        payment_score += 8
    if payment_data.get("method"):
        payment_score += 6
    if payment_data.get("due_date"):
        payment_score += 6
    scores["payment_terms"] = payment_score
    
    # SLA definition scoring (15 points)
    sla_score = 0
    sla_data = extracted_data.get("sla", {})
    if sla_data.get("availability"):
        sla_score += 7
    if sla_data.get("response_times") and len(sla_data.get("response_times", {})) > 0:
        sla_score += 8
    scores["sla_definition"] = sla_score
    
    # Contact information scoring (10 points)
    contact_score = 0
    account_data = extracted_data.get("account_info", {})
    if account_data.get("billing_contact", {}).get("email"):
        contact_score += 5
    if account_data.get("billing_contact", {}).get("phone"):
        contact_score += 3
    if account_data.get("account_number"):
        contact_score += 2
    scores["contact_information"] = contact_score
    
    # Calculate overall score
    scores["overall"] = sum([
        scores["party_identification"],
        scores["financial_completeness"], 
        scores["payment_terms"],
        scores["sla_definition"],
        scores["contact_information"]
    ])
    
    return scores

def identify_gaps(extracted_data: dict[str, Any]) -> list[str]:
    """Identify missing critical information"""
    gaps = []
    
    # Check party information
    party_data = extracted_data.get("party", {})
    if not party_data.get("service_provider", {}).get("name"):
        gaps.append("Service provider name not identified")
    if not party_data.get("customer", {}).get("name"):
        gaps.append("Customer name not identified")
    
    # Check financial details
    financial_data = extracted_data.get("financial_details", {})
    if not financial_data.get("total_value"):
        gaps.append("Total contract value not found")
    
    # Check payment structure
    payment_data = extracted_data.get("payment_structure", {})
    if not payment_data.get("terms"):
        gaps.append("Payment terms not defined")
    if not payment_data.get("method"):
        gaps.append("Payment method not specified")
    
    # Check SLA
    sla_data = extracted_data.get("sla", {})
    if not sla_data.get("availability"):
        gaps.append("Service availability target not defined")
    if not sla_data.get("response_times") or len(sla_data.get("response_times", {})) == 0:
        gaps.append("Support response times not specified")
    
    # Check contact information
    account_data = extracted_data.get("account_info", {})
    if not account_data.get("billing_contact", {}).get("email"):
        gaps.append("Billing contact email not found")
    
    return gaps