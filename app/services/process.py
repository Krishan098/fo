from pypdf import PdfReader
import io
import re
import spacy
from typing import Any
def extractContractId(file:io.BytesIO):
    file.seek(0)
    reader=PdfReader(file)
    page= reader.pages[0]
    text=(page.extract_text())
    pattern = re.search(r"Contract\s*ID\s*:\s*([A-Za-z0-9\-_]+)", text, re.IGNORECASE)
    if pattern:
        return pattern.group(1).strip()
    return "UNKNOWN"

nlp=spacy.load("en_core_web_sm")

def extractParty(text:str)->dict[str,Any]:
    doc=nlp(text)
    parties={"service_provider":{},"customer":{},"authorized_reps":[]}
    lines = text.splitlines()
    service_provider_block = []
    customer_block = []
    rep_block = []
    capture = None
    for line in lines:
        if "Service Provider:" in line:
            capture = "service_provider"
            continue
        elif "Customer:" in line:
            capture = "customer"
            continue
        elif "Authorized Representatives" in line:
            capture = "authorized_reps"
            continue
        elif line.strip() == "":
            capture = None

        if capture == "service_provider":
            service_provider_block.append(line.strip())
        elif capture == "customer":
            customer_block.append(line.strip())
        elif capture == "authorized_reps":
            rep_block.append(line.strip())

    for ent in nlp("\n".join(service_provider_block)).ents:
        if ent.label_ == "ORG":
            parties["service_provider"]["name"] = ent.text
        if ent.label_ == "GPE":
            parties["service_provider"]["location"] = ent.text

    for ent in nlp("\n".join(customer_block)).ents:
        if ent.label_ == "ORG":
            parties["customer"]["name"] = ent.text
        if ent.label_ == "GPE":
            parties["customer"]["location"] = ent.text

    for ent in nlp("\n".join(rep_block)).ents:
        if ent.label_ == "PERSON":
            parties["authorized_reps"].append(ent.text)

    return parties

def extractAccInformation(text: str) -> dict[str, Any]:
    doc = nlp(text)
    info = {"account_number": None, "billing_contact": {}}

    for ent in doc.ents:
        if ent.label_ == "CARDINAL" and "Account Number" in text:
            info["account_number"] = ent.text
        if ent.label_ == "PERSON" and "Accounts Receivable" in text:
            info["billing_contact"]["name"] = ent.text
        if ent.label_ == "EMAIL":
            info["billing_contact"]["email"] = ent.text
        if ent.label_ == "PHONE":
            info["billing_contact"]["phone"] = ent.text

    return info


def extract_financial_details(text: str) -> dict[str, Any]:
    doc = nlp(text)
    financials = {"line_items": [], "total_value": None, "currency": None}

    for ent in doc.ents:
        if ent.label_ == "MONEY":
            if financials["total_value"] is None:
                financials["total_value"] = ent.text
            else:
                financials["line_items"].append(ent.text)

    if financials["total_value"]:
        if "$" in financials["total_value"]:
            financials["currency"] = "USD"

    return financials

def extract_payment_structure(text: str) -> dict[str, Any]:
    structure = {"terms": None, "method": None, "due_date": None}
    if "Net 30" in text:
        structure["terms"] = "Net 30"
    elif "Net 60" in text:
        structure["terms"] = "Net 60"

    if "ACH" in text:
        structure["method"] = "ACH transfer"
    if "30th" in text:
        structure["due_date"] = "30th of each month"

    return structure

def extract_revenue_classification(text: str) -> dict[str, Any]:
    classification = {"recurring": False, "one_time": False, "auto_renewal": False}

    if "Monthly Recurring" in text:
        classification["recurring"] = True
    if "One-Time Setup" in text:
        classification["one_time"] = True
    if "auto-renews" in text.lower():
        classification["auto_renewal"] = True

    return classification

def extract_sla(text: str) -> dict[str, Any]:
    doc = nlp(text)
    sla = {"availability": None, "response_times": {}, "penalties": []}

    if "99.9%" in text:
        sla["availability"] = "99.9% uptime"

    for line in text.splitlines():
        if "Critical issues" in line:
            sla["response_times"]["critical"] = "1 hour"
        if "High priority" in line:
            sla["response_times"]["high"] = "4 hours"
        if "Medium priority" in line:
            sla["response_times"]["medium"] = "8 hours"
        if "Low priority" in line:
            sla["response_times"]["low"] = "24 hours"
        if "credit" in line.lower():
            sla["penalties"].append(line.strip())

    return sla