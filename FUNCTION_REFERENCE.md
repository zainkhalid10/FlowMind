# FlowMind - Function and Algorithm Location Reference

## Complete Function Mapping with Line Numbers

This document provides a comprehensive mapping of all functions, classes, and algorithms in the FlowMind codebase with their exact line numbers and purposes.

---

## CORE FILES

### flowmind.py (Main Application File)

**Classes:**
- None (uses imported classes)

**Functions:**

**Line 46:** `_summarize_image_ocr(ocr_text, context)` 
- **Purpose:** Legacy OCR summarization wrapper
- **Task:** Delegates to enhanced OCR summarization service
- **Algorithm:** Text summarization

**Line 252:** `_vlm_summarize(image_path, context)`
- **Purpose:** Visual Language Model image summarization wrapper
- **Task:** Delegates to enhanced VLM summarization service
- **Algorithm:** Multi-model VLM aggregation

**Line 285:** `_analyze_document_internal(file, user_id, db_session, progress_tracker_id)`
- **Purpose:** Main document analysis function
- **Task:** Extracts text, images, and OCR from uploaded documents
- **Algorithms Used:**
  - PDF text extraction (PyPDF)
  - DOCX text extraction (python-docx)
  - PPTX text extraction (python-pptx)
  - Image extraction and OCR (Tesseract)
  - Progress tracking
- **Line Range:** 285-680

**Line 2953:** `_analyze_with_agent_internal(file, user_id, db_session, progress_tracker_id)`
- **Purpose:** AI agent-based document analysis
- **Task:** Processes documents using RAG agent for requirements extraction
- **Algorithms Used:**
  - Document text extraction
  - RAG agent processing
  - Requirements extraction
  - Self-learning pattern application
- **Line Range:** 2953-3400

**Line 98:** `favicon()`
- **Purpose:** Favicon endpoint handler
- **Task:** Returns empty favicon to prevent 404 errors

**Line 2554:** `get_records(current_user)`
- **Purpose:** Display all analyzed file summaries
- **Task:** HTML page showing user's uploaded files

---

### rag_agent.py (RAG Agent and AI Processing)

**Classes:**

**Line 15:** `RequirementsExtractionAgent`
- **Purpose:** Main RAG agent class for requirements extraction
- **Task:** Handles document processing, requirements extraction, and self-learning
- **Key Methods:**
  - `__init__()` - Line 16: Agent initialization
  - `_init_learning_system()` - Line 135: Initialize self-learning components
  - `_load_learned_patterns()` - Line 180: Load patterns from ChromaDB
  - `_save_learned_patterns()` - Line 210: Save patterns to ChromaDB
  - `_learn_from_extraction()` - Line 260: Learn from successful extractions
  - `_extract_category_specific_patterns()` - Line 356: Extract patterns by category
  - `_learn_document_context()` - Line 382: Learn document context patterns
  - `_apply_learned_patterns()` - Line 455: Apply learned patterns to new text
  - `_update_performance_metrics()` - Line 568: Track extraction performance
  - `_save_performance_metrics()` - Line 602: Save performance data
  - `get_learning_status()` - Line 630: Get learning statistics
  - `_format_learned_results()` - Line 665: Format learning results
  - `_parse_response_to_sections()` - Line 684: Parse extraction response
  - `_normalize_line()` - Line 726: Normalize text lines
  - `_should_keep_line()` - Line 762: Filter relevant lines
  - `_format_sections()` - Line 871: Format extracted sections
  - `_learn_from_results()` - Line 907: Learn from extraction results
  - `_spacy_filter()` - Line 932: spaCy-based sentence filtering
  - `_near_duplicate_filter()` - Line 956: Near-duplicate detection algorithm
  - `_rerank()` - Line 990: Cross-encoder reranking algorithm
  - `_llm_finalize()` - Line 1005: LLM-based text finalization
  - `_create_tools()` - Line 1051: Create agent tools
  - `_create_agent()` - Line 1150: Create agent executor
  - `process_document()` - Line 1202: Process document and create vector store
  - `_heuristic_extract()` - Line 1232: Heuristic requirements extraction algorithm
  - `_semantic_extract()` - Line 1453: Semantic requirements extraction algorithm
  - `extract_requirements()` - Line 1800: Main requirements extraction method
  - `search_requirements()` - Line 1942: Search requirements in vector store
  - `search_specific_requirements()` - Line 1951: Search specific requirement types

**Functions:**

**Line 1973:** `get_agent(user_id)`
- **Purpose:** Get or create agent instance with caching
- **Task:** Agent factory function with user-specific caching
- **Algorithm:** Singleton pattern with user-specific instances

---

### auth.py (Authentication)

**Functions:**

**Line 26:** `get_password_hash(password)`
- **Purpose:** Hash password using bcrypt
- **Task:** Secure password hashing
- **Algorithm:** bcrypt with salt (72-byte limit)

**Line 39:** `verify_password(plain_password, hashed_password)`
- **Purpose:** Verify password against hash
- **Task:** Password verification with backward compatibility
- **Algorithm:** bcrypt verification with SHA-256 fallback

**Line 78:** `create_access_token(data, expires_delta)`
- **Purpose:** Create JWT access token
- **Task:** Generate authentication tokens
- **Algorithm:** JWT (HS256) with 30-day expiry

**Line 93:** `get_db()`
- **Purpose:** Database session dependency
- **Task:** Provide database session with automatic cleanup
- **Algorithm:** Dependency injection with context manager

**Line 102:** `get_current_user(credentials, db)`
- **Purpose:** Get authenticated user from JWT token
- **Task:** Validate token and return user object
- **Algorithm:** JWT token validation

**Line 137:** `get_current_user_optional(credentials, db)`
- **Purpose:** Get user if authenticated, None otherwise
- **Task:** Optional authentication for public endpoints
- **Algorithm:** JWT token validation with optional error

---

### database.py (Database Models)

**Classes:**

**Line 27:** `ParsedFile(Base)`
- **Purpose:** Database model for parsed files
- **Task:** Store document metadata and extracted text
- **Fields:** id, filename, extracted_text, detected_shapes, summary, full_text_path, user_id, created_at, view_id

**Line 47:** `ImageMeta(Base)`
- **Purpose:** Database model for image metadata
- **Task:** Store image information from documents
- **Fields:** id, file_id, image_path, page_number, ocr_text

**Line 60:** `User(Base)`
- **Purpose:** Database model for users
- **Task:** Store user account information
- **Fields:** id, email, username, hashed_password, created_at, is_active

**Functions:**

**Line 72:** `init_db()`
- **Purpose:** Initialize database tables
- **Task:** Create all database tables if they don't exist
- **Algorithm:** SQLAlchemy table creation

---

## ROUTE FILES

### routes/auth_routes.py

**Functions:**

**Line 17:** `SignupRequest` (Pydantic Model)
- **Purpose:** Signup request validation model

**Line 23:** `LoginRequest` (Pydantic Model)
- **Purpose:** Login request validation model

**Line 27:** `signup(request, db)`
- **Purpose:** User registration endpoint
- **Task:** Create new user account
- **Algorithm:** Password hashing, user creation, token generation
- **Line Range:** 27-88

**Line 89:** `login(request, db)`
- **Purpose:** User authentication endpoint
- **Task:** Authenticate user and return token
- **Algorithm:** Password verification, token generation
- **Line Range:** 89-136

**Line 137:** `get_current_user_info(token, credentials, db)`
- **Purpose:** Get current user information
- **Task:** Return authenticated user details
- **Line Range:** 137-191

---

### routes/upload_routes.py

**Functions:**

**Line 20:** `validate_file_extension(filename)`
- **Purpose:** Validate file extension
- **Task:** Check if file type is allowed
- **Algorithm:** Extension whitelist validation

**Line 25:** `validate_file_size(file_size)`
- **Purpose:** Validate file size
- **Task:** Check if file is within size limits
- **Algorithm:** Size limit check (50MB default)

**Line 30:** `upload_client_doc(file, current_user, db, background_tasks)`
- **Purpose:** Basic document upload endpoint
- **Task:** Upload and extract text from document
- **Algorithm:** Document parsing, text extraction, progress tracking
- **Line Range:** 30-71

**Line 74:** `upload_agent_doc(file, current_user, db)`
- **Purpose:** AI agent document analysis endpoint
- **Task:** Upload and analyze document with RAG agent
- **Algorithm:** Document processing, RAG agent analysis, requirements extraction
- **Line Range:** 74-117

**Line 120:** `get_progress(tracker_id)`
- **Purpose:** Get progress for document processing
- **Task:** Return real-time progress updates
- **Line Range:** 120-129

---

### routes/dashboard_routes.py

**Functions:**

**Line 15:** `dashboard_page()`
- **Purpose:** Dashboard HTML page
- **Task:** Serve dashboard HTML

**Line 25:** `extract_page()`
- **Purpose:** Extract page HTML
- **Task:** Serve extract page HTML

**Line 36:** `_get_user_from_token(token, credentials, db)`
- **Purpose:** Helper to get user from token
- **Task:** Extract user from JWT token (query param or header)
- **Algorithm:** JWT token validation
- **Line Range:** 36-71

**Line 74:** `get_my_uploads(token, credentials, db)`
- **Purpose:** Get user's uploaded files
- **Task:** Return list of user's documents
- **Algorithm:** Database query with user filtering
- **Line Range:** 74-109

**Line 112:** `get_upload_details(upload_id, token, credentials, db)`
- **Purpose:** Get detailed upload information
- **Task:** Return specific upload details
- **Line Range:** 112-143

---

### routes/training_routes.py

**Functions:**

**Line 14:** `training_page()`
- **Purpose:** Training status HTML page
- **Task:** Serve training dashboard HTML

**Line 224:** `get_training_status(token, credentials, db)`
- **Purpose:** Get model training status
- **Task:** Return learning statistics and patterns
- **Algorithm:** Agent retrieval, pattern counting, statistics aggregation
- **Line Range:** 224-365

---

## SERVICE FILES

### services/document_service.py

**Functions:**

**Line 8:** `analyze_document(file, user_id, db, progress_tracker_id)`
- **Purpose:** Document analysis service wrapper
- **Task:** Analyze document and save with user_id
- **Algorithm:** Delegates to _analyze_document_internal

**Line 15:** `analyze_with_agent(file, user_id, db, progress_tracker_id)`
- **Purpose:** AI agent analysis service wrapper
- **Task:** Analyze document with RAG agent and save with user_id
- **Algorithm:** Delegates to _analyze_with_agent_internal

---

### services/image_service.py

**Functions:**

**Line 9:** `_get_env_bool(key, default)`
- **Purpose:** Get boolean from environment variable
- **Task:** Parse environment variable to boolean

**Line 15:** `enhanced_vlm_summarize(image_path, context, image_type)`
- **Purpose:** Enhanced VLM image summarization
- **Task:** Summarize images using Visual Language Models
- **Algorithm:** Multi-model VLM aggregation, response deduplication, frequency ranking
- **Line Range:** 15-191

**Line 194:** `enhanced_ocr_summarize(ocr_text, context)`
- **Purpose:** Enhanced OCR text summarization
- **Task:** Summarize OCR-extracted text
- **Algorithm:** Context-aware text analysis, key information extraction
- **Line Range:** 194-291

---

### services/progress_service.py

**Classes:**

**Line 1:** `ProcessingStage` (Enum)
- **Purpose:** Document processing stages
- **Values:** UPLOADING, PARSING, TEXT_EXTRACTION, IMAGE_DETECTION, OCR_PROCESSING, IMAGE_SUMMARIZATION, FINALIZING

---

### services/progress_storage.py

**Classes:**

**Line 1:** `ProgressTracker`
- **Purpose:** Track document processing progress
- **Task:** Manage progress state and updates
- **Methods:**
  - `start()` - Initialize tracker
  - `set_stage()` - Update processing stage
  - `complete()` - Mark as complete
  - `get_progress()` - Get current progress

**Functions:**

**Line 1:** `create_progress_tracker()`
- **Purpose:** Create new progress tracker
- **Task:** Generate tracker ID and instance

**Line 1:** `get_progress_tracker(tracker_id)`
- **Purpose:** Get existing progress tracker
- **Task:** Retrieve tracker by ID

**Line 1:** `remove_progress_tracker(tracker_id)`
- **Purpose:** Remove progress tracker
- **Task:** Clean up tracker after completion

---

## UTILITY FILES

### utils/async_helpers.py

**Functions:**

**Line 15:** `run_in_thread(func, *args, timeout, **kwargs)`
- **Purpose:** Run blocking function in thread pool with timeout
- **Task:** Execute synchronous functions asynchronously
- **Algorithm:** ThreadPoolExecutor with asyncio timeout
- **Line Range:** 15-49

**Line 52:** `with_timeout(timeout)`
- **Purpose:** Decorator to add timeout to async functions
- **Task:** Apply timeout to async functions
- **Algorithm:** asyncio.wait_for wrapper
- **Line Range:** 52-65

---

## KEY ALGORITHMS AND THEIR LOCATIONS

### 1. Requirements Extraction Algorithm
**Location:** rag_agent.py
- **Heuristic Method:** Line 1232 - `_heuristic_extract()`
  - Pattern matching: Lines 1247-1400
  - Scoring system: Lines 1349-1397
  - Deduplication: Lines 1398-1452
- **Semantic Method:** Line 1453 - `_semantic_extract()`
  - Embedding generation: Lines 1470-1490
  - Cosine similarity: Lines 1496-1510
  - Top-K selection: Lines 1511-1550
- **Main Entry:** Line 1800 - `extract_requirements()`

### 2. Self-Learning Algorithm
**Location:** rag_agent.py
- **Pattern Loading:** Line 180 - `_load_learned_patterns()`
- **Pattern Saving:** Line 210 - `_save_learned_patterns()`
- **Learning from Extraction:** Line 260 - `_learn_from_extraction()`
- **Category Pattern Extraction:** Line 356 - `_extract_category_specific_patterns()`
- **Document Context Learning:** Line 382 - `_learn_document_context()`
- **Pattern Application:** Line 455 - `_apply_learned_patterns()`

### 3. Text Chunking Algorithm
**Location:** rag_agent.py, Line 82-86
- **Implementation:** RecursiveCharacterTextSplitter
- **Parameters:** chunk_size=1000, overlap=200

### 4. Similarity Search Algorithm
**Location:** rag_agent.py
- **Vector Store Creation:** Line 1211 - Chroma.from_documents()
- **Similarity Search:** Line 1051 - search_requirements() tool
- **Top-K Retrieval:** Uses ChromaDB similarity_search with k parameter

### 5. Deduplication Algorithm
**Location:** rag_agent.py, Line 956 - `_near_duplicate_filter()`
- **Method:** Embedding-based similarity
- **Threshold:** 0.92 (92% similarity)
- **Algorithm:** Cosine similarity comparison with set-based deduplication

### 6. Reranking Algorithm
**Location:** rag_agent.py, Line 990 - `_rerank()`
- **Model:** BAAI/bge-reranker-base (optional)
- **Method:** Cross-encoder reranking
- **Purpose:** Improve search result relevance

### 7. Image Summarization Algorithm
**Location:** services/image_service.py, Line 15 - `enhanced_vlm_summarize()`
- **Process:** Multi-model VLM aggregation
- **Steps:**
  - Base64 encoding: Line 30-31
  - Prompt generation: Lines 34-86
  - Model querying: Lines 100-115
  - Response aggregation: Lines 120-191
  - Deduplication: Lines 121-133
  - Frequency ranking: Lines 135-191

### 8. OCR Text Summarization Algorithm
**Location:** services/image_service.py, Line 194 - `enhanced_ocr_summarize()`
- **Process:** Context-aware text analysis
- **Steps:**
  - Text preprocessing: Lines 200-220
  - Key information extraction: Lines 221-250
  - Summary generation: Lines 251-291

### 9. Document Parsing Algorithms
**Location:** flowmind.py
- **PDF Parsing:** Line 325-500 - PyPDF text and image extraction
- **DOCX Parsing:** Line 550-580 - python-docx text extraction
- **PPTX Parsing:** Line 580-610 - python-pptx text extraction
- **Image OCR:** Line 362-500 - Tesseract OCR processing

### 10. Password Hashing Algorithm
**Location:** auth.py
- **Hashing:** Line 26 - `get_password_hash()` - bcrypt with salt
- **Verification:** Line 39 - `verify_password()` - bcrypt check with SHA-256 fallback

### 11. JWT Token Algorithm
**Location:** auth.py
- **Token Creation:** Line 78 - `create_access_token()` - HS256 algorithm
- **Token Validation:** Line 102 - `get_current_user()` - JWT decode and validation

### 12. Async Thread Pool Algorithm
**Location:** utils/async_helpers.py
- **Thread Execution:** Line 15 - `run_in_thread()` - ThreadPoolExecutor with asyncio timeout
- **Timeout Management:** asyncio.wait_for with configurable timeout

---

## SUMMARY BY TASK

### Document Processing
- **Main Function:** flowmind.py:285 - `_analyze_document_internal()`
- **PDF Parsing:** flowmind.py:325-500
- **DOCX Parsing:** flowmind.py:550-580
- **PPTX Parsing:** flowmind.py:580-610
- **Text Extraction:** flowmind.py:314-610

### AI/ML Processing
- **Agent Initialization:** rag_agent.py:16 - `__init__()`
- **Document Processing:** rag_agent.py:1202 - `process_document()`
- **Requirements Extraction:** rag_agent.py:1800 - `extract_requirements()`
- **Heuristic Extraction:** rag_agent.py:1232 - `_heuristic_extract()`
- **Semantic Extraction:** rag_agent.py:1453 - `_semantic_extract()`

### Self-Learning
- **Pattern Loading:** rag_agent.py:180 - `_load_learned_patterns()`
- **Pattern Saving:** rag_agent.py:210 - `_save_learned_patterns()`
- **Learning:** rag_agent.py:260 - `_learn_from_extraction()`
- **Pattern Application:** rag_agent.py:455 - `_apply_learned_patterns()`

### Image Processing
- **VLM Summarization:** services/image_service.py:15 - `enhanced_vlm_summarize()`
- **OCR Summarization:** services/image_service.py:194 - `enhanced_ocr_summarize()`
- **Image Extraction:** flowmind.py:362-500

### Authentication
- **Password Hashing:** auth.py:26 - `get_password_hash()`
- **Password Verification:** auth.py:39 - `verify_password()`
- **Token Creation:** auth.py:78 - `create_access_token()`
- **User Authentication:** auth.py:102 - `get_current_user()`

### Database Operations
- **Session Management:** auth.py:93 - `get_db()`
- **Table Creation:** database.py:72 - `init_db()`
- **Models:** database.py:27, 47, 60 - ParsedFile, ImageMeta, User

### API Endpoints
- **Signup:** routes/auth_routes.py:27 - `signup()`
- **Login:** routes/auth_routes.py:89 - `login()`
- **Upload Basic:** routes/upload_routes.py:30 - `upload_client_doc()`
- **Upload AI:** routes/upload_routes.py:74 - `upload_agent_doc()`
- **Dashboard:** routes/dashboard_routes.py:74 - `get_my_uploads()`
- **Training Status:** routes/training_routes.py:224 - `get_training_status()`

---

This reference document provides exact line numbers for all functions, classes, and algorithms in the FlowMind codebase, making it easy to locate specific implementations and understand the code structure.

