from typing import Annotated
from app.services.process import extractContractId
from app.services.parse import process_contract
from fastapi import FastAPI, UploadFile,File,HTTPException,BackgroundTasks
from fastapi.responses import HTMLResponse
import io
from typing import Any
import uuid
app = FastAPI()
processing_status: dict[str, dict[str, Any]] = {}
processing_results: dict[str, dict[str, Any]] = {}
@app.post("/contracts/upload/")
async def create_upload_contracts(background_tasks:BackgroundTasks,contracts: Annotated[list[UploadFile]|None,File(description="Multiple contracts as UploadContracts")]):
    contract_ids=[]
    if not contracts:
        return {"message":"No file uploaded"}
    else:
        for i in contracts:
            if i.content_type!="application/pdf":
                raise HTTPException(status_code=422,detail="Only accepts PDFs for contracts")
            bytess=await i.read()
            buffer=io.BytesIO(bytess)
            contract_id = extractContractId(buffer)
            contract_ids.append(contract_id)
            processing_status[contract_id]={"state": "pending", "progress": 0}
            background_tasks.add_task(process_contract, contract_id,bytess,i.filename)

    return {"contract_ids": contract_ids,"filename":i.filename}


@app.get("/contracts/{contract_id}/status")
async def get_contract_status(contract_id: str):
    if contract_id not in processing_status:
        raise HTTPException(status_code=404, detail="Contract ID not found")

    status = processing_status[contract_id]
    result = processing_results.get(contract_id)
    return {"status": status, "results": result if status["state"] == "completed" else None}
@app.get("/")
async def main():
    content = """
<body>
<form action="/contracts/upload" enctype="multipart/form-data" method="post">
<input name="contracts" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)