# **Contract Intelligence Parser - Technical Assignment**

## **Problem Statement**

You are tasked with building a contract intelligence system for an accounts receivable SaaS platform. The system needs to automatically process contracts, extract critical financial and operational data.

## **Business Context**

Modern businesses handle hundreds of contracts with varying formats, terms, and structures. Manual contract review is time-consuming and error-prone, leading to missed revenue opportunities, payment delays, and compliance issues. Your solution should automate contract analysis while providing confidence scores and gap identification for business users.

## **Technical Requirements**

### **Core System Architecture**
- **Backend**: Python-based REST API
- **Database**: MongoDB
- **Frontend**: React/Next.js web application
- **Deployment**: Fully dockerized solution
- **Processing**: Asynchronous contract parsing with status tracking

### **API Endpoints**

**1. Contract Upload** (POST `/contracts/upload`)
- Accept PDF contract files
- Return immediate response with `contract_id`
- Initiate background processing
- Non-blocking operation

**2. Processing Status** (GET `/contracts/{contract_id}/status`)
- Check parsing progress using contract ID
- Return processing state: `pending`, `processing`, `completed`, `failed`
- Include progress percentage and error details if applicable

**3. Contract Data** (GET `/contracts/{contract_id}`)
- Return parsed contract data in JSON format
- Include extracted fields and confidence scores
- Available only when processing is complete

**4. Contract List** (GET `/contracts`)
- Return paginated list of all contracts
- Include filtering capabilities (by status, date, score, etc.)
- Support sorting and search functionality (optional)

**5. Contract Download** (GET `/contracts/{contract_id}/download`)
- Download original contract file
- Maintain file integrity and proper headers

### **Optional: Unit test for backend**

- Write unit tests with at least 60% code coverage

### **Data Extraction Requirements**

Extract and structure the following information:

**1. Party Identification**
- Contract parties (customer, vendor, third parties)
- Legal entity names and registration details
- Authorized signatories and roles

**2. Account Information**
- Customer billing details
- Account numbers and references
- Contact information for billing/technical support

**3. Financial Details**
- Line items with descriptions, quantities, and unit prices
- Total contract value and currency
- Tax information and additional fees

**4. Payment Structure**
- Payment terms (Net 30, Net 60, etc.)
- Payment schedules and due dates
- Payment methods and banking details

**5. Revenue Classification**
- Identify recurring vs. one-time payments or both
- Subscription models and billing cycles
- Renewal terms and auto-renewal clauses

**6. Service Level Agreements**
- Performance metrics and benchmarks
- Penalty clauses and remedies
- Support and maintenance terms

### **Scoring Algorithm**

**Weighted Scoring System (0-100 points)**
- Financial completeness: 30 points
- Party identification: 25 points
- Payment terms clarity: 20 points
- SLA definition: 15 points
- Contact information: 10 points

**Gap Analysis**
- Explicitly identify missing critical fields

### **Frontend Requirements**

**User Interface Features**
- Drag-and-drop contract upload
- Contract list with (optional: filtering, sorting, and search)
- Detailed contract view with extracted data visualization
- Responsive design for desktop and mobile (optional)

**User Experience**
- Intuitive navigation and clean interface
- Clear indication of data confidence levels

### **Technical Constraints**

- **Performance**: Handle contracts up to 50MB
- **Scalability**: Support concurrent processing of multiple contracts
- **Reliability**: Implement proper error handling and retry mechanisms
- **Security**: Secure file handling and data storage
- **Documentation**: Comprehensive README with setup instructions

### **Success Criteria**

Your solution will be evaluated on:

1. **Functionality**: All endpoints work as specified
2. **Accuracy**: Reliable extraction of contract data
3. **Performance**: Efficient processing and responsive UI
4. **Code Quality**: Clean, maintainable, and well-documented code
5. **System Design**: Proper architecture and error handling
6. **User Experience**: Intuitive interface and workflow
7. **Deployment**: Easy setup using Docker

**Timeline**: 3 days from assignment start

**Note**: 
- I have provided one sample contract. You should research a few more contract formats, find test documents, and design the extraction logic based on industry standards and business requirements. 
- Test it with a few cases of missing information, unsupported file type etc.
- You can use LLM for coding
