# FlowMind - Complete Technology Stack and Algorithms Documentation

## Table of Contents
1. Core Framework & Web Server
2. Database & ORM
3. AI/ML Libraries & Models
4. Document Processing Libraries
5. Image Processing & OCR
6. Authentication & Security
7. API Calls & External Services
8. Core Algorithms
9. Data Structures
10. Utilities & Helper Libraries

---

## 1. CORE FRAMEWORK & WEB SERVER

### FastAPI (v0.104.1)
- **Purpose**: Modern, fast web framework for building APIs
- **Usage**: Main application framework, REST API endpoints, request/response handling
- **Key Features Used**:
  - Async/await support
  - Automatic API documentation
  - Dependency injection
  - Request validation with Pydantic
  - File upload handling
  - CORS middleware

### Uvicorn (v0.24.0)
- **Purpose**: ASGI server for running FastAPI application
- **Usage**: Production server, handles HTTP requests, WebSocket support
- **Configuration**: Standard workers, auto-reload for development

### Python (3.9+)
- **Purpose**: Primary programming language
- **Version**: Python 3.9 or higher
- **Key Modules Used**:
  - asyncio (async operations)
  - concurrent.futures (ThreadPoolExecutor)
  - hashlib (hashing algorithms)
  - base64 (encoding/decoding)
  - json (data serialization)
  - os, shutil (file system operations)
  - uuid (unique ID generation)
  - logging (application logging)
  - warnings (warning suppression)

---

## 2. DATABASE & ORM

### SQLAlchemy (v2.0.36)
- **Purpose**: Python SQL toolkit and Object-Relational Mapping (ORM)
- **Usage**: Database models, queries, session management
- **Features Used**:
  - Declarative base models
  - Relationship mapping (one-to-many)
  - Session management with dependency injection
  - Connection pooling (pool_size=10, max_overflow=20)
  - Connection recycling (pool_recycle=3600)

### SQLite
- **Purpose**: Embedded relational database
- **Usage**: Primary data storage
- **Database File**: flowmind.db
- **Tables**:
  - users (user accounts, authentication)
  - parsed_files (uploaded documents metadata)
  - image_meta (image metadata from documents)

---

## 3. AI/ML LIBRARIES & MODELS

### LangChain (v0.1.0)
- **Purpose**: Framework for developing applications powered by language models
- **Components Used**:
  - **AgentExecutor**: Agent execution framework
  - **create_react_agent**: ReAct agent creation
  - **Tool**: Tool interface for agent actions
  - **RecursiveCharacterTextSplitter**: Text chunking (chunk_size=1000, overlap=200)
  - **Document**: Document schema
  - **PromptTemplate**: Prompt templating
  - **ConversationBufferMemory**: Conversation memory management
  - **Chroma**: Vector store integration

### LangChain Community (v0.0.10)
- **Purpose**: Community integrations for LangChain
- **Components Used**:
  - **HuggingFaceEmbeddings**: Embedding model wrapper
  - **Chroma**: Vector database integration

### ChromaDB (v0.4.18)
- **Purpose**: Open-source embedding database
- **Usage**: Vector storage for RAG (Retrieval-Augmented Generation)
- **Features Used**:
  - Persistent storage (./chroma_db directory)
  - Collection management (user-specific collections)
  - Similarity search
  - Metadata filtering
  - Embedding storage and retrieval
- **Collections**:
  - requirements_documents (document chunks)
  - global_requirements (global requirements)
  - learning_patterns_user_{user_id} (user-specific learning)
  - extraction_performance_user_{user_id} (performance metrics)

### Sentence Transformers (v2.2.2)
- **Purpose**: State-of-the-art sentence embeddings
- **Model Used**: sentence-transformers/all-MiniLM-L6-v2
- **Usage**: Text embedding generation for semantic search
- **Fallback**: MD5-based heuristic embeddings if model unavailable
- **Features**:
  - 384-dimensional embeddings
  - Fast inference
  - Multilingual support

### HuggingFace Hub
- **Purpose**: Model repository and download
- **Usage**: Downloading and caching embedding models
- **Model**: all-MiniLM-L6-v2 (384 dimensions)

---

## 4. DOCUMENT PROCESSING LIBRARIES

### PyPDF (v3.17.4)
- **Purpose**: PDF document parsing
- **Usage**: Extract text and images from PDF files
- **Features Used**:
  - Page-by-page text extraction
  - Image extraction from PDFs
  - Metadata extraction
  - Multi-page document handling

### python-docx (v1.1.0)
- **Purpose**: Microsoft Word document processing
- **Usage**: Extract text and images from .docx files
- **Features Used**:
  - Paragraph extraction
  - Image extraction
  - Document structure parsing

### python-pptx (v0.6.23)
- **Purpose**: Microsoft PowerPoint presentation processing
- **Usage**: Extract text and images from .pptx files
- **Features Used**:
  - Slide-by-slide text extraction
  - Image extraction from slides
  - Presentation structure parsing

---

## 5. IMAGE PROCESSING & OCR

### Tesseract OCR (via pytesseract v0.3.10)
- **Purpose**: Optical Character Recognition
- **Usage**: Extract text from images within documents
- **Configuration**: Platform-aware path detection (macOS, Windows, Linux)
- **Features**:
  - Multi-language OCR
  - Image preprocessing
  - Text extraction from scanned documents

### Pillow/PIL (v11.0.0)
- **Purpose**: Python Imaging Library
- **Usage**: Image manipulation and processing
- **Features Used**:
  - Image opening and reading
  - Format conversion
  - Image metadata extraction
  - Image preprocessing for OCR

### OpenCV (opencv-python v4.8.1.78)
- **Purpose**: Computer vision library
- **Usage**: Image processing and analysis
- **Features Used**:
  - Image preprocessing
  - Contour detection
  - Shape detection
  - Image thresholding
  - Grayscale conversion

---

## 6. AUTHENTICATION & SECURITY

### python-jose (v3.3.0) with cryptography
- **Purpose**: JWT (JSON Web Token) implementation
- **Usage**: User authentication tokens
- **Algorithm**: HS256 (HMAC-SHA256)
- **Token Expiry**: 30 days
- **Features**:
  - Token encoding/decoding
  - Token validation
  - User ID extraction from tokens

### bcrypt (via passlib v1.7.4)
- **Purpose**: Password hashing
- **Usage**: Secure password storage
- **Algorithm**: bcrypt with salt
- **Configuration**: 72-byte password limit (truncated if longer)
- **Features**:
  - Secure password hashing
  - Password verification
  - Backward compatibility with SHA-256 (legacy)

### HTTPBearer
- **Purpose**: FastAPI security scheme
- **Usage**: Bearer token authentication
- **Implementation**: Token in Authorization header or query parameter

---

## 7. API CALLS & EXTERNAL SERVICES

### Ollama API (Local)
- **Endpoint**: http://localhost:11434/api/generate
- **Purpose**: Local LLM inference for VLM (Visual Language Model) and text generation
- **Models Used**:
  - llava:13b (default VLM model for image summarization)
  - llama3:8b (default LLM for text finalization)
- **Configuration**: Environment variables
  - FLOWMIND_VLM_MODELS (comma-separated list)
  - FLOWMIND_OLLAMA_VLM_MODEL (default: llava:13b)
  - FLOWMIND_OLLAMA_MODEL (default: llama3:8b)
  - FLOWMIND_VLM_TIMEOUT_MS (default: 12000ms)
- **Usage**:
  - Image summarization via VLM
  - Text finalization and polishing
  - Requirements extraction enhancement

### OpenRouter API (Optional)
- **Purpose**: Cloud-based LLM API alternative
- **Configuration**: OPENROUTER_API_KEY environment variable
- **Usage**: Fallback LLM service if Ollama unavailable
- **Status**: Optional, not required for core functionality

### CDN Services (Frontend)
- **Bootstrap 5.3.2**: CSS framework (cdn.jsdelivr.net)
- **Font Awesome 6.4.0**: Icons (cdnjs.cloudflare.com)
- **Google Fonts**: Inter font family (fonts.googleapis.com)

---

## 8. CORE ALGORITHMS

### 1. Requirements Extraction Algorithm
**Type**: Hybrid Heuristic + Semantic Search
**Location**: rag_agent.py - _heuristic_extract() and _semantic_extract()

**Heuristic Method**:
- Pattern-based keyword matching
- Category classification (functional, non-functional, user, system, business, features)
- Scoring system based on keyword strength (strong, moderate, weak)
- Sentence scoring and ranking
- Deduplication algorithm
- Pattern matching with regex

**Semantic Method**:
- Text embedding using sentence-transformers
- Cosine similarity calculation
- Category-specific prompt matching
- Top-K selection per category
- Similarity-based ranking

**Hybrid Approach**:
- Combines both methods
- Fallback mechanism
- Performance tracking
- Method selection based on success rates

### 2. Self-Learning Algorithm
**Type**: Pattern Learning and Adaptation
**Location**: rag_agent.py - _learn_from_extraction()

**Process**:
1. Extract patterns from successful extractions
2. Store patterns in ChromaDB collections
3. Load patterns on initialization
4. Apply learned patterns to new documents
5. Update pattern frequency and success rates
6. Category-specific pattern learning

**Data Structures**:
- Keywords (set-based storage)
- Phrases (set-based storage)
- Patterns (set-based storage)
- Performance metrics (dictionary)

### 3. Text Chunking Algorithm
**Type**: Recursive Character Text Splitting
**Location**: langchain.text_splitter.RecursiveCharacterTextSplitter

**Parameters**:
- chunk_size: 1000 characters
- chunk_overlap: 200 characters
- length_function: len()

**Purpose**: Split large documents into manageable chunks for embedding

### 4. Similarity Search Algorithm
**Type**: Vector Similarity Search
**Location**: ChromaDB + LangChain

**Process**:
1. Generate embeddings for query text
2. Calculate cosine similarity with stored embeddings
3. Return top-K most similar documents
4. Rank results by similarity score

**Configuration**:
- Default k=5 for search
- k=10 for specific requirement extraction
- k=20 for document summarization

### 5. Deduplication Algorithm
**Type**: Near-Duplicate Detection
**Location**: rag_agent.py - _near_duplicate_filter()

**Method**:
- Embedding-based similarity
- Threshold: 0.92 (92% similarity)
- Cosine similarity comparison
- Set-based deduplication

### 6. Reranking Algorithm
**Type**: Cross-Encoder Reranking (Optional)
**Location**: rag_agent.py - _rerank()

**Model**: BAAI/bge-reranker-base (if enabled)
**Purpose**: Improve search result relevance
**Configuration**: FLOWMIND_USE_RERANKER environment variable

### 7. Image Summarization Algorithm
**Type**: Multi-Model VLM Aggregation
**Location**: services/image_service.py - enhanced_vlm_summarize()

**Process**:
1. Base64 encode image
2. Generate context-aware prompts
3. Query multiple VLM models (if available)
4. Aggregate responses
5. Deduplicate and rank by frequency
6. Return consolidated summary

**Prompt Types**:
- Diagram analysis (architecture, data flow)
- Chart analysis (data trends, metrics)
- Workflow analysis (process steps, states)
- Generic analysis (general image content)

### 8. OCR Text Summarization Algorithm
**Type**: Context-Aware Text Summarization
**Location**: services/image_service.py - enhanced_ocr_summarize()

**Process**:
1. Extract OCR text from image
2. Analyze text structure and content
3. Identify key information
4. Generate concise summary
5. Context integration from surrounding document

---

## 9. DATA STRUCTURES

### Database Models (SQLAlchemy)
- **User**: id, email, username, hashed_password, created_at, is_active
- **ParsedFile**: id, filename, extracted_text, detected_shapes, summary, full_text_path, user_id, created_at, view_id
- **ImageMeta**: id, file_id, image_path, page_number, ocr_text

### In-Memory Data Structures
- **learned_patterns**: Dictionary with category keys, each containing keywords, phrases, patterns (sets)
- **extraction_stats**: Dictionary tracking performance metrics
- **REQUIREMENTS_VIEWS**: Dictionary storing extraction results by view_id
- **agent_cache**: Dictionary caching agent instances by user_id
- **progress_trackers**: Dictionary tracking document processing progress

### Vector Store Structures
- **Document chunks**: Stored with metadata (source, chunk_id)
- **Learning patterns**: Stored with metadata (category, type)
- **Performance metrics**: Stored with metadata (type, timestamp)

---

## 10. UTILITIES & HELPER LIBRARIES

### python-dotenv (v1.0.1)
- **Purpose**: Environment variable management
- **Usage**: Load configuration from .env file
- **Configuration Variables**:
  - SECRET_KEY (JWT secret)
  - TESSERACT_CMD (Tesseract path)
  - FLOWMIND_USE_VLM (enable VLM)
  - FLOWMIND_VLM_MODELS (VLM model list)
  - FLOWMIND_OLLAMA_VLM_MODEL (default VLM model)
  - FLOWMIND_OLLAMA_MODEL (default LLM model)
  - FLOWMIND_USE_SPACY (enable spaCy)
  - FLOWMIND_USE_RERANKER (enable reranker)
  - FLOWMIND_USE_LLM_FINALIZE (enable LLM finalization)
  - FLOWMIND_ENABLE_SELF_LEARNING (enable learning)
  - OPENROUTER_API_KEY (optional)
  - MAX_FILE_SIZE (file size limit)

### requests (v2.32.3)
- **Purpose**: HTTP library for API calls
- **Usage**: 
  - Ollama API requests
  - OpenRouter API requests (optional)
  - External service communication

### python-multipart (v0.0.6)
- **Purpose**: Multipart form data handling
- **Usage**: File upload processing in FastAPI

### asyncio
- **Purpose**: Asynchronous programming
- **Usage**: 
  - Async endpoint handlers
  - Concurrent operations
  - Timeout management
  - Thread pool execution

### concurrent.futures
- **Purpose**: Parallel execution
- **Usage**: 
  - ThreadPoolExecutor for blocking operations
  - Async wrapper for synchronous functions
  - Timeout handling

### Custom Utilities
- **utils/async_helpers.py**: Async wrapper functions, timeout management
- **services/document_service.py**: Document analysis service layer
- **services/image_service.py**: Image processing and summarization
- **services/progress_service.py**: Progress tracking
- **services/progress_storage.py**: Progress state management

---

## 11. ARCHITECTURE PATTERNS

### Design Patterns Used
1. **Dependency Injection**: FastAPI's Depends() for database sessions and authentication
2. **Repository Pattern**: Service layer abstraction
3. **Singleton Pattern**: Agent instance caching
4. **Factory Pattern**: Agent creation with user-specific configuration
5. **Strategy Pattern**: Multiple extraction methods (heuristic, semantic, hybrid)
6. **Observer Pattern**: Progress tracking system

### Async Architecture
- **Async/Await**: All endpoints are async
- **Thread Pool**: Blocking operations run in thread pool
- **Timeout Management**: All long operations have timeouts
- **Non-blocking I/O**: Database and file operations are non-blocking

### Caching Strategy
- **Agent Caching**: User-specific agent instances cached
- **Training Status Caching**: 5-second TTL cache
- **Progress Tracking**: In-memory progress state
- **ChromaDB Persistence**: Vector store persists across restarts

---

## 12. SECURITY FEATURES

### Authentication
- JWT tokens with 30-day expiry
- Bearer token authentication
- Token validation on every request
- User session management

### Password Security
- bcrypt hashing with salt
- 72-byte password limit
- Backward compatibility with legacy SHA-256

### File Security
- File type validation (whitelist approach)
- File size limits (50MB default)
- Path traversal prevention
- Secure file storage

### API Security
- CORS middleware configuration
- Input validation with Pydantic
- SQL injection prevention (SQLAlchemy ORM)
- Error message sanitization

---

## 13. PERFORMANCE OPTIMIZATIONS

### Database
- Connection pooling (10 base, 20 overflow)
- Connection recycling (1 hour)
- Indexed columns (user_id, created_at, view_id, email, username)
- Query optimization

### Caching
- Agent instance caching
- Training status caching (5s TTL)
- ChromaDB persistent storage
- In-memory progress tracking

### Async Operations
- Non-blocking I/O
- Thread pool for CPU-intensive tasks
- Timeout handling
- Concurrent request processing

### Resource Management
- Proper session cleanup
- Memory-efficient text processing
- Chunked document processing
- Lazy loading of models

---

## 14. MONITORING & LOGGING

### Logging
- Python logging module
- Structured log messages
- Error tracking
- Performance metrics logging

### Progress Tracking
- Real-time progress updates
- Stage-based progress (uploading, parsing, processing, finalizing)
- Percentage completion
- Estimated time remaining

### Performance Metrics
- Extraction method success rates
- Category accuracy tracking
- Learning iteration counts
- Document processing statistics

---

## 15. DEPLOYMENT & CONFIGURATION

### Server
- Uvicorn ASGI server
- Auto-reload for development
- Production-ready configuration
- Port: 8000 (default)

### Environment Configuration
- .env file support
- Environment variable overrides
- Platform-aware configuration (macOS, Windows, Linux)
- Default fallback values

### File Storage
- Local file system storage
- Uploads directory: ./uploads
- ChromaDB directory: ./chroma_db
- Database file: ./flowmind.db

---

## SUMMARY

**Total Technologies**: 30+ libraries and frameworks
**Primary Language**: Python 3.9+
**Main Framework**: FastAPI
**Database**: SQLite + SQLAlchemy
**Vector Database**: ChromaDB
**AI/ML**: LangChain, Sentence Transformers, HuggingFace
**Document Processing**: PyPDF, python-docx, python-pptx
**Image Processing**: Tesseract OCR, Pillow, OpenCV
**Authentication**: JWT, bcrypt
**External APIs**: Ollama (local), OpenRouter (optional)

**Core Algorithms**:
1. Hybrid Requirements Extraction (Heuristic + Semantic)
2. Self-Learning Pattern Recognition
3. Vector Similarity Search
4. Multi-Model VLM Aggregation
5. Near-Duplicate Detection
6. Cross-Encoder Reranking
7. Context-Aware Text Summarization

This comprehensive technology stack enables FlowMind to provide intelligent document analysis, requirements extraction, and continuous learning capabilities.

