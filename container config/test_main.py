import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
import io
from backend.main import app, ContractProcessor, contracts_db, file_storage, ContractScore

client = TestClient(app)

@pytest.fixture
def sample_pdf_content():
    """Create a mock PDF content for testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n178\n%%EOF"

@pytest.fixture
def mock_cohere_response():
    """Mock Cohere API response."""
    return {
        "parties": [
            {
                "name": "Acme Corp",
                "legal_entity": "Acme Corporation LLC",
                "registration_details": "Delaware Registration",
                "signatories": ["John Doe"],
                "roles": ["CEO"]
            }
        ],
        "account_info": {
            "billing_details": "123 Main St, City, State",
            "account_numbers": ["ACC-12345"],
            "contact_info": "billing@acme.com"
        },
        "financial_details": {
            "line_items": [
                {
                    "description": "Software License",
                    "quantity": 1.0,
                    "unit_price": 1000.0,
                    "total_price": 1000.0
                }
            ],
            "total_value": 1000.0,
            "currency": "USD",
            "tax_info": "Tax included",
            "additional_fees": []
        },
        "payment_structure": {
            "payment_terms": "Net 30",
            "payment_schedule": ["Monthly"],
            "due_dates": ["2024-01-31"],
            "payment_methods": ["Bank Transfer"],
            "banking_details": "Bank ABC, Account 123456"
        },
        "revenue_classification": {
            "revenue_type": "recurring",
            "billing_cycle": "Monthly",
            "renewal_terms": "Auto-renewal",
            "auto_renewal": True
        },
        "sla": {
            "performance_metrics": ["99.9% uptime"],
            "penalty_clauses": ["5% discount for downtime"],
            "support_terms": ["24/7 support"],
            "maintenance_terms": ["Monthly maintenance window"]
        }
    }

@pytest.fixture(autouse=True)
def clear_storage():
    """Clear in-memory storage before each test."""
    contracts_db.clear()
    file_storage.clear()
    yield
    contracts_db.clear()
    file_storage.clear()

class TestContractAPI:
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Contract Intelligence Parser API" in response.json()["message"]
    
    def test_upload_contract_invalid_file_type(self):
        """Test upload with invalid file type."""
        files = {"file": ("test.txt", b"test content", "text/plain")}
        response = client.post("/contracts/upload", files=files)
        assert response.status_code == 400
        assert "Only PDF files are supported" in response.json()["detail"]
    
    def test_upload_contract_too_large(self):
        """Test upload with file too large."""
        large_content = b"0" * (51 * 1024 * 1024)  # 51MB
        files = {"file": ("large.pdf", large_content, "application/pdf")}
        response = client.post("/contracts/upload", files=files)
        assert response.status_code == 400
        assert "File size exceeds 50MB limit" in response.json()["detail"]
    
    @patch('main.processor.process_contract')
    def test_upload_contract_success(self, mock_process, sample_pdf_content):
        """Test successful contract upload."""
        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}
        response = client.post("/contracts/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "contract_id" in data
        assert data["status"] == "uploaded"
        assert "Contract processing initiated" in data["message"]
    
    def test_get_contract_status_not_found(self):
        """Test getting status for non-existent contract."""
        response = client.get("/contracts/nonexistent/status")
        assert response.status_code == 404
        assert "Contract not found" in response.json()["detail"]
    
    def test_get_contract_data_not_found(self):
        """Test getting data for non-existent contract."""
        response = client.get("/contracts/nonexistent")
        assert response.status_code == 404
        assert "Contract not found" in response.json()["detail"]
    
    def test_get_contracts_empty(self):
        """Test getting contracts when none exist."""
        response = client.get("/contracts")
        assert response.status_code == 200
        data = response.json()
        assert data["contracts"] == []
        assert data["total"] == 0
    
    def test_download_contract_not_found(self):
        """Test downloading non-existent contract."""
        response = client.get("/contracts/nonexistent/download")
        assert response.status_code == 404
        assert "Contract not found" in response.json()["detail"]

class TestContractProcessor:
    
    def test_calculate_score_complete_contract(self, mock_cohere_response):
        """Test score calculation for complete contract."""
        processor = ContractProcessor()
        score = processor.calculate_score(mock_cohere_response)
        
        assert isinstance(score, ContractScore)
        assert score.total_score > 80  # Should be high for complete contract
        assert score.financial_completeness > 0
        assert score.party_identification > 0
        assert score.payment_terms_clarity > 0
        assert score.sla_definition > 0
        assert score.contact_information > 0
    
    def test_calculate_score_incomplete_contract(self):
        """Test score calculation for incomplete contract."""
        processor = ContractProcessor()
        incomplete_data = {
            "parties": [],
            "account_info": {},
            "financial_details": {},
            "payment_structure": {},
            "revenue_classification": {},
            "sla": {}
        }
        
        score = processor.calculate_score(incomplete_data)
        
        assert isinstance(score, ContractScore)
        assert score.total_score == 0  # Should be 0 for empty contract
        assert len(score.missing_fields) > 0  # Should have missing fields
        assert "Contract parties" in score.missing_fields
        assert "Line items" in score.missing_fields
    
    @patch('main.PyPDF2.PdfReader')
    async def test_extract_text_from_pdf(self, mock_pdf_reader):
        """Test PDF text extraction."""
        # Mock PDF reader
        mock_page = Mock()
        mock_page.extract_text.return_value = "Test contract content"
        mock_pdf_reader.return_value.pages = [mock_page]
        
        processor = ContractProcessor()
        result = await processor.extract_text_from_pdf(b"fake pdf content")
        
        assert result == "Test contract content\n"
    
    @patch('cohere.ClientV2.chat')
    async def test_parse_contract_with_cohere(self, mock_chat, mock_cohere_response):
        """Test contract parsing with Cohere API."""
        # Mock Cohere response
        mock_response = Mock()
        mock_response.message.content = [Mock()]
        mock_response.message.content[0].text = json.dumps(mock_cohere_response)
        mock_chat.return_value = mock_response
        
        processor = ContractProcessor()
        result = await processor.parse_contract_with_cohere("Test contract text")
        
        assert result == mock_cohere_response
        mock_chat.assert_called_once()
    
    @patch('cohere.ClientV2.chat')
    async def test_parse_contract_cohere_error(self, mock_chat):
        """Test contract parsing when Cohere API fails."""
        mock_chat.side_effect = Exception("API Error")
        
        processor = ContractProcessor()
        result = await processor.parse_contract_with_cohere("Test contract text")
        
        # Should return empty structure on error
        assert result["parties"] == []
        assert result["account_info"] == {}

class TestIntegration:
    
    @patch('main.processor.parse_contract_with_cohere')
    @patch('main.processor.extract_text_from_pdf')
    def test_full_contract_processing_flow(self, mock_extract, mock_parse, sample_pdf_content, mock_cohere_response):
        """Test full contract processing workflow."""
        mock_extract.return_value = "Test contract content"
        mock_parse.return_value = mock_cohere_response
        
        # Upload contract
        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/contracts/upload", files=files)
        assert upload_response.status_code == 200
        
        contract_id = upload_response.json()["contract_id"]
        
        # Wait a bit for background processing
        import time
        time.sleep(0.1)
        
        # Check status
        status_response = client.get(f"/contracts/{contract_id}/status")
        assert status_response.status_code == 200
        
        # The contract should be in contracts_db
        assert contract_id in contracts_db
    
    def test_contract_lifecycle(self, sample_pdf_content):
        """Test complete contract lifecycle: upload -> status -> delete."""
        # Upload
        files = {"file": ("lifecycle_test.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/contracts/upload", files=files)
        contract_id = upload_response.json()["contract_id"]
        
        # Check status
        status_response = client.get(f"/contracts/{contract_id}/status")
        assert status_response.status_code == 200
        
        # Delete
        delete_response = client.delete(f"/contracts/{contract_id}")
        assert delete_response.status_code == 200
        
        # Verify deletion
        status_response = client.get(f"/contracts/{contract_id}/status")
        assert status_response.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=main", "--cov-report=html"])