# FlowMind - Complete Function Reference

## Table of Contents
1. [Core Application Functions](#core-application-functions)
2. [RAG Agent Functions](#rag-agent-functions)
3. [Authentication Functions](#authentication-functions)
4. [Database Functions](#database-functions)
5. [Document Processing Functions](#document-processing-functions)
6. [Image Processing Functions](#image-processing-functions)
7. [Route Handlers](#route-handlers)
8. [Service Functions](#service-functions)
9. [Utility Functions](#utility-functions)

---

## Core Application Functions

### `flowmind.py`

#### Document Analysis Functions

**`_analyze_document_internal(file, user_id, db_session, progress_tracker_id)`**
- **Purpose**: Internal function that extracts text, images, and OCR from uploaded documents
- **Parameters**:
  - `file`: UploadFile object
  - `user_id`: Integer user ID
  - `db_session`: SQLAlchemy session
  - `progress_tracker_id`: Optional progress tracker ID
- **Returns**: Dictionary with extracted text, image metadata, and summaries
- **Key Features**:
  - Supports PDF, DOCX, PPTX, TXT, and image files
  - Extracts images and performs OCR
  - Generates VLM summaries for images
  - Saves results to database
- **File Formats Supported**: PDF, DOCX, PPTX, TXT, PNG, JPG, JPEG

**`_analyze_with_agent_internal(file, user_id, db_session, progress_tracker_id, basic_extraction_data)`**
- **Purpose**: AI-powered document analysis using RAG agent with optional basic extraction data merging
- **Parameters**:
  - `file`: UploadFile object
  - `user_id`: Integer user ID
  - `db_session`: SQLAlchemy session
  - `progress_tracker_id`: Optional progress tracker ID
  - `basic_extraction_data`: Optional dictionary with basic extraction results
- **Returns**: Dictionary with AI-extracted requirements and features
- **Key Features**:
  - Merges basic extraction data with AI analysis
  - Processes document with RAG agent
  - Extracts requirements and saves features
  - Returns comprehensive analysis results

**`parse_and_save_features(requirements_text, user_id, file_id, db, image_summaries)`**
- **Purpose**: Parse extracted requirements text and save as features in database
- **Parameters**:
  - `requirements_text`: String containing extracted requirements
  - `user_id`: Integer user ID
  - `file_id`: Integer file ID
  - `db`: Database session
  - `image_summaries`: Optional list of image summaries
- **Returns**: Integer count of saved features
- **Key Features**:
  - Parses requirements by category
  - Deduplicates features
  - Calculates quality scores
  - Saves to database with proper categorization

#### Image Processing Functions

**`_vlm_summarize(image_path, context)`**
- **Purpose**: Generate AI summary of image using Vision-Language Model
- **Parameters**:
  - `image_path`: String path to image file
  - `context`: Optional string context about the image
- **Returns**: String summary of image content
- **Key Features**:
  - Uses Ollama VLM if available
  - Falls back to OCR-based summarization
  - Provides intelligent image interpretation

**`_summarize_image_ocr(ocr_text, context)`**
- **Purpose**: Legacy function that uses enhanced OCR summarization service
- **Parameters**:
  - `ocr_text`: String OCR text from image
  - `context`: Optional string context
- **Returns**: String enhanced summary

#### Public API Functions

**`@app.get("/api/public/stats")`**
- **Purpose**: Get public statistics about learned patterns
- **Returns**: JSON with total learned items (keywords, patterns, phrases)
- **Key Features**:
  - Aggregates from global and user-specific agents
  - Falls back to database count if needed
  - No authentication required

---

## RAG Agent Functions

### `rag_agent.py`

#### Core Agent Functions

**`RequirementsExtractionAgent.__init__(api_key, user_id)`**
- **Purpose**: Initialize the RAG agent for requirements extraction
- **Parameters**:
  - `api_key`: API key (not used currently)
  - `user_id`: Optional user ID for user-specific learning
- **Key Features**:
  - Initializes embeddings (HuggingFace or fallback)
  - Sets up ChromaDB vector store
  - Configures text splitter
  - Enables self-learning if configured

**`process_document(text, filename)`**
- **Purpose**: Process a document and add it to the vector store
- **Parameters**:
  - `text`: String document text
  - `filename`: String filename
- **Returns**: Dictionary with status and processing results
- **Key Features**:
  - Splits text into chunks
  - Creates embeddings
  - Stores in ChromaDB
  - Returns processing statistics

**`extract_requirements(query)`**
- **Purpose**: Extract requirements from processed documents using multiple methods
- **Parameters**:
  - `query`: Optional query string
- **Returns**: Dictionary with extracted requirements
- **Key Features**:
  - Tries multiple extraction methods (heuristic, pattern, semantic)
  - Applies learned patterns
  - Selects best result
  - Enhances output for professional wording
  - Returns formatted requirements by category

#### Extraction Methods

**`_heuristic_extract(text)`**
- **Purpose**: Pattern-based keyword matching extraction
- **Parameters**: `text`: String document text
- **Returns**: Dictionary with categorized requirements
- **Key Features**:
  - Fast pattern matching
  - Keyword-based classification
  - Quality scoring
  - Deduplication

**`_semantic_extract(text, top_k_per_class)`**
- **Purpose**: Embedding-based similarity extraction
- **Parameters**:
  - `text`: String document text
  - `top_k_per_class`: Integer top results per category
- **Returns**: Dictionary with semantically extracted requirements
- **Key Features**:
  - Uses sentence embeddings
  - Semantic similarity matching
  - Category-specific prompts
  - Learned pattern boosting

**`_advanced_pattern_extract(text)`**
- **Purpose**: Advanced regex and NLP pattern extraction
- **Parameters**: `text`: String document text
- **Returns**: Dictionary with pattern-matched requirements
- **Key Features**:
  - Complex regex patterns
  - Category-specific patterns
  - Enhanced deduplication
  - Quality filtering

#### Text Processing Functions

**`_normalize_line(line)`**
- **Purpose**: Normalize requirement text for processing
- **Parameters**: `line`: String text line
- **Returns**: Normalized string
- **Key Features**:
  - Removes bullet symbols
  - Normalizes whitespace
  - Removes image metadata markers
  - Cleans punctuation

**`_should_keep_line(line)`**
- **Purpose**: Filter out non-requirement lines
- **Parameters**: `line`: String text line
- **Returns**: Boolean indicating if line should be kept
- **Key Features**:
  - Filters metadata
  - Filters image markers
  - Filters headings
  - Checks for requirement indicators

**`_enhance_requirement_text(requirement)`**
- **Purpose**: Enhance requirement text to be more professional
- **Parameters**: `requirement`: String requirement text
- **Returns**: Enhanced string
- **Key Features**:
  - Improves wording
  - Replaces vague terms
  - Standardizes technical terms
  - Ensures proper formatting

**`_enhance_final_output(section_text)`**
- **Purpose**: Enhance entire output for professional presentation
- **Parameters**: `section_text`: String formatted sections
- **Returns**: Enhanced string
- **Key Features**:
  - Preserves structure
  - Enhances individual requirements
  - Maintains quality indicators

**`_format_sections(sections)`**
- **Purpose**: Format extracted requirements into user-friendly output
- **Parameters**: `sections`: Dictionary of categorized requirements
- **Returns**: Formatted string
- **Key Features**:
  - Adds quality indicators (✅, ⚠️, ❌)
  - Sorts by priority
  - Calculates quality scores
  - Formats with proper structure

#### Classification Functions

**`_classify_requirement_improved(sentence, context)`**
- **Purpose**: Classify requirement into category with context awareness
- **Parameters**:
  - `sentence`: String requirement sentence
  - `context`: Optional string context
- **Returns**: String category name
- **Categories**: functional, non_functional, user, business, system, features
- **Key Features**:
  - Context-aware classification
  - Domain detection
  - Pattern matching
  - Priority-based classification

**`_score_requirement_quality(requirement)`**
- **Purpose**: Calculate quality score for a requirement (0-100)
- **Parameters**: `requirement`: String requirement text
- **Returns**: Float quality score
- **Key Features**:
  - Length scoring
  - Action verb detection
  - Specificity scoring
  - Vague term penalties

#### Learning Functions

**`_learn_from_results(filename, sections)`**
- **Purpose**: Learn from extracted requirements and store patterns
- **Parameters**:
  - `filename`: String source filename
  - `sections`: Dictionary of categorized requirements
- **Key Features**:
  - Stores in ChromaDB
  - Persists learned patterns
  - User-specific learning support

**`_apply_learned_patterns(text)`**
- **Purpose**: Apply previously learned patterns to new text
- **Parameters**: `text`: String document text
- **Returns**: Dictionary with learned requirements
- **Key Features**:
  - Semantic similarity search
  - Pattern matching
  - Boosts relevant requirements

**`_save_learned_patterns()`**
- **Purpose**: Save learned patterns to persistent storage
- **Key Features**:
  - User-specific storage
  - Global pattern storage
  - ChromaDB persistence

#### Deduplication Functions

**`_cross_category_deduplicate(categorized)`**
- **Purpose**: Remove duplicates across all categories
- **Parameters**: `categorized`: Dictionary of categorized requirements
- **Returns**: Deduplicated dictionary
- **Key Features**:
  - Normalization-based deduplication
  - Core content matching
  - Semantic similarity detection

**`_reclassify_and_deduplicate_all(initial_categories)`**
- **Purpose**: Reclassify and deduplicate all requirements
- **Parameters**: `initial_categories`: Dictionary of initial categories
- **Returns**: Reclassified and deduplicated dictionary

---

## Authentication Functions

### `auth.py`

**`get_password_hash(password)`**
- **Purpose**: Hash password using bcrypt
- **Parameters**: `password`: String password
- **Returns**: String hashed password
- **Key Features**:
  - Handles 72-byte bcrypt limit
  - Secure salt generation

**`verify_password(plain_password, hashed_password)`**
- **Purpose**: Verify password against hash
- **Parameters**:
  - `plain_password`: String plain password
  - `hashed_password`: String hashed password
- **Returns**: Boolean indicating match
- **Key Features**:
  - Supports bcrypt format
  - Backward compatible with SHA-256

**`create_access_token(data, expires_delta)`**
- **Purpose**: Create JWT access token
- **Parameters**:
  - `data`: Dictionary with token data
  - `expires_delta`: Optional timedelta for expiration
- **Returns**: String JWT token
- **Key Features**:
  - 30-day expiration by default
  - Secure JWT encoding

**`get_current_user(credentials, db)`**
- **Purpose**: Get authenticated user from JWT token
- **Parameters**:
  - `credentials`: HTTPAuthorizationCredentials
  - `db`: Database session
- **Returns**: User object
- **Raises**: HTTPException if invalid

**`get_current_user_optional(credentials, db)`**
- **Purpose**: Get user if authenticated, None otherwise
- **Parameters**:
  - `credentials`: Optional HTTPAuthorizationCredentials
  - `db`: Database session
- **Returns**: User object or None

**`get_db()`**
- **Purpose**: Database session dependency
- **Returns**: Database session generator
- **Key Features**:
  - Automatic session cleanup
  - Proper connection management

---

## Database Functions

### `database.py`

**`init_db()`**
- **Purpose**: Initialize database tables
- **Key Features**:
  - Creates all tables
  - Handles migrations
  - Sets up relationships

#### Database Models

**`ParsedFile`**
- **Table**: `parsed_files`
- **Fields**:
  - `id`: Primary key
  - `filename`: String filename
  - `extracted_text`: Text extracted content
  - `detected_shapes`: Integer image count
  - `summary`: Text summary
  - `full_text_path`: String path to text file
  - `user_id`: Foreign key to users
  - `created_at`: DateTime timestamp
  - `view_id`: String view identifier
- **Relationships**: images, user, features

**`ImageMeta`**
- **Table**: `image_meta`
- **Fields**:
  - `id`: Primary key
  - `file_id`: Foreign key to parsed_files
  - `image_path`: String path to image
  - `page_number`: Integer page number
  - `ocr_text`: Text OCR content
- **Relationships**: file

**`User`**
- **Table**: `users`
- **Fields**:
  - `id`: Primary key
  - `email`: String unique email
  - `username`: String unique username
  - `hashed_password`: String password hash
  - `created_at`: DateTime timestamp
  - `is_active`: Integer active status
- **Relationships**: parsed_files, features

**`Feature`**
- **Table**: `features`
- **Fields**:
  - `id`: Primary key
  - `user_id`: Foreign key to users
  - `file_id`: Foreign key to parsed_files
  - `category`: String requirement category
  - `description`: Text requirement description
  - `status`: String approval status
  - `quality_score`: Integer quality score
  - `feedback`: Text client feedback
  - `created_at`: DateTime timestamp
  - `updated_at`: DateTime last update
- **Relationships**: user, file

---

## Document Processing Functions

### `services/document_service.py`

**`analyze_document(file, user_id, db, progress_tracker_id)`**
- **Purpose**: Analyze document and save with user_id
- **Parameters**:
  - `file`: UploadFile object
  - `user_id`: Integer user ID
  - `db`: Database session
  - `progress_tracker_id`: Optional tracker ID
- **Returns**: Dictionary with extraction results
- **Key Features**:
  - Wraps internal analysis function
  - Handles user association
  - Progress tracking support

**`analyze_with_agent(file, user_id, db, progress_tracker_id, basic_extraction_data)`**
- **Purpose**: Analyze document with AI agent
- **Parameters**:
  - `file`: UploadFile object
  - `user_id`: Integer user ID
  - `db`: Database session
  - `progress_tracker_id`: Optional tracker ID
  - `basic_extraction_data`: Optional basic extraction results
- **Returns**: Dictionary with AI analysis results
- **Key Features**:
  - Merges basic extraction data
  - AI-powered analysis
  - Feature extraction
  - Progress tracking

---

## Image Processing Functions

### `services/image_service.py`

**`comprehensive_image_interpretation(image_path, context)`**
- **Purpose**: Complete image interpretation combining OCR, VLM, and analysis
- **Parameters**:
  - `image_path`: String path to image
  - `context`: Optional string context
- **Returns**: Dictionary with interpretation results
- **Key Features**:
  - Advanced OCR extraction
  - Image type detection
  - VLM analysis (if enabled)
  - Merged interpretation

**`enhanced_vlm_analyze(image_path, ocr_text, image_type, context)`**
- **Purpose**: Enhanced VLM analysis of image
- **Parameters**:
  - `image_path`: String path to image
  - `ocr_text`: String OCR text
  - `image_type`: String detected image type
  - `context`: Optional string context
- **Returns**: Dictionary with VLM analysis
- **Key Features**:
  - Vision-Language Model processing
  - Context-aware analysis
  - Requirement extraction from images

**`enhanced_ocr_summarize(ocr_text, context)`**
- **Purpose**: Enhanced OCR text summarization
- **Parameters**:
  - `ocr_text`: String OCR text
  - `context`: Optional string context
- **Returns**: String enhanced summary
- **Key Features**:
  - Intelligent text analysis
  - Context integration
  - Requirement extraction

**`detect_image_type_advanced(image_path, ocr_text)`**
- **Purpose**: Detect image type with advanced analysis
- **Parameters**:
  - `image_path`: String path to image
  - `ocr_text`: String OCR text
- **Returns**: Dictionary with type and confidence
- **Key Features**:
  - Multiple image type detection
  - Confidence scoring
  - Pattern recognition

---

## Route Handlers

### `routes/auth_routes.py`

**`@router.post("/api/signup")`**
- **Purpose**: User registration
- **Returns**: JWT token and user info
- **Key Features**: Email validation, password hashing

**`@router.post("/api/login")`**
- **Purpose**: User authentication
- **Returns**: JWT token and user info
- **Key Features**: Password verification, token generation

### `routes/upload_routes.py`

**`@router.post("/upload_client_doc")`**
- **Purpose**: Basic document extraction
- **Returns**: JSON with extracted text and images
- **Key Features**: Progress tracking, user association

**`@router.post("/upload_agent_doc")`**
- **Purpose**: AI agent document analysis
- **Parameters**: Optional basic extraction data
- **Returns**: JSON with AI-extracted requirements
- **Key Features**: Merges basic extraction, AI analysis

**`@router.get("/api/progress/{tracker_id}")`**
- **Purpose**: Get processing progress
- **Returns**: Progress status and percentage

### `routes/approval_routes.py`

**`@router.get("/api/features")`**
- **Purpose**: Get features for approval
- **Returns**: List of features with pagination
- **Key Features**: Filters by user, run, status

**`@router.put("/api/features/{feature_id}")`**
- **Purpose**: Update feature (approve/deny)
- **Returns**: Updated feature
- **Key Features**: Status updates, feedback support

**`@router.put("/api/features/{feature_id}/feedback")`**
- **Purpose**: Update feature feedback
- **Returns**: Updated feature
- **Key Features**: Client feedback storage

**`@router.delete("/api/features/cleanup/old")`**
- **Purpose**: Delete all features for user
- **Returns**: Deletion count
- **Key Features**: Preserves patterns and learning

### `routes/dashboard_routes.py`

**`@router.get("/dashboard")`**
- **Purpose**: Serve dashboard page
- **Returns**: HTML dashboard

**`@router.get("/api/dashboard/stats")`**
- **Purpose**: Get dashboard statistics
- **Returns**: JSON with user stats

### `routes/training_routes.py`

**`@router.get("/training")`**
- **Purpose**: Serve training page
- **Returns**: HTML training dashboard

**`@router.get("/api/training-status")`**
- **Purpose**: Get training/learning status
- **Returns**: JSON with learned patterns statistics
- **Key Features**: Aggregates from agents, counts learned items

---

## Service Functions

### `services/progress_service.py`

**`ProcessingStage` (Enum)**
- **Stages**: UPLOADING, PARSING, TEXT_EXTRACTION, IMAGE_DETECTION, OCR_PROCESSING, IMAGE_SUMMARIZATION, FINALIZING, COMPLETE

### `services/progress_storage.py`

**`create_progress_tracker()`**
- **Purpose**: Create new progress tracker
- **Returns**: Tracker ID and tracker object

**`get_progress_tracker(tracker_id)`**
- **Purpose**: Get progress tracker by ID
- **Returns**: Tracker object or None

**`remove_progress_tracker(tracker_id)`**
- **Purpose**: Remove progress tracker
- **Key Features**: Cleanup and memory management

---

## Utility Functions

### `utils/async_helpers.py`

**`run_in_thread(func, *args, timeout, **kwargs)`**
- **Purpose**: Run function in thread pool with timeout
- **Parameters**:
  - `func`: Function to run
  - `*args`: Function arguments
  - `timeout`: Optional timeout in seconds
  - `**kwargs`: Function keyword arguments
- **Returns**: Function result
- **Key Features**:
  - Non-blocking execution
  - Timeout handling
  - Exception propagation

---

## Helper Functions

### Text Processing

**`_normalize_line(line)`**: Normalize text for processing
**`_should_keep_line(line)`**: Filter non-requirements
**`_enhance_requirement_text(requirement)`**: Improve wording
**`_is_valid_requirement(sentence)`**: Validate requirement

### Classification

**`_classify_requirement_improved(sentence, context)`**: Categorize requirement
**`_detect_domain_context(text)`**: Detect domain/context
**`_score_requirement_quality(requirement)`**: Calculate quality score

### Deduplication

**`_cross_category_deduplicate(categorized)`**: Remove duplicates
**`_reclassify_and_deduplicate_all(initial_categories)`**: Reclassify and dedupe
**`_near_duplicate_filter(items)`**: Filter near-duplicates

### Learning

**`_learn_from_results(filename, sections)`**: Learn from extraction
**`_apply_learned_patterns(text)`**: Apply learned patterns
**`_save_learned_patterns()`**: Persist learning

---

## Global Functions

**`get_agent(user_id)`**
- **Purpose**: Get or create RAG agent instance
- **Parameters**: `user_id`: Optional user ID
- **Returns**: RequirementsExtractionAgent instance
- **Key Features**:
  - Caching for performance
  - User-specific agents
  - Global agent fallback

---

## Notes

- All functions include comprehensive error handling
- Most functions support async/await for non-blocking operations
- Progress tracking is integrated throughout processing pipeline
- User-specific learning enables personalized improvements
- Quality scoring provides feedback on requirement quality
- Deduplication ensures clean, unique requirements
