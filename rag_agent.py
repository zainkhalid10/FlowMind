import os
import json
import re
from typing import List, Dict, Any, Optional
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import chromadb
from chromadb.config import Settings

class RequirementsExtractionAgent:
    def __init__(self, api_key: str, user_id: Optional[int] = None):
        """Initialize the RAG agent for requirements extraction.
        
        Args:
            api_key: API key (not used currently)
            user_id: Optional user ID for user-specific learning
        """
        self.api_key = ""  # Gemini removed; no API key used
        self.user_id = user_id  # Store user ID for user-specific learning
        
        # No LLM; rely on open-source embeddings + heuristic extraction
        self.llm = None
        self.model_name = "heuristic"
        
        # Initialize embeddings: prefer HuggingFace all-MiniLM-L6-v2; fallback to simple hash
        self.embeddings = None
        print("🤖 Initializing AI models...")
        try:
            print("📦 Loading HuggingFace embeddings model: sentence-transformers/all-MiniLM-L6-v2")
            # Try to import sentence_transformers first to check if it's available
            try:
                import sentence_transformers
                print(f"✅ sentence_transformers package found (version: {getattr(sentence_transformers, '__version__', 'unknown')})")
            except ImportError as import_err:
                print(f"⚠️ sentence_transformers package not available: {import_err}")
                raise import_err
            
            self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            self.model_name = "hf-all-MiniLM-L6-v2"
            print(f"✅ Embeddings model loaded successfully: {self.model_name}")
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Failed to load HuggingFace embeddings: {error_msg}")
            if "cached_download" in error_msg or "huggingface_hub" in error_msg.lower():
                print("💡 Tip: Try updating packages: pip install --upgrade sentence-transformers huggingface_hub")
            print("🔄 Falling back to heuristic embeddings...")
            class SimpleEmbeddings:
                def embed_documents(self, texts):
                    import hashlib
                    output = []
                    for text in texts:
                        h = hashlib.md5((text or "").encode()).digest()
                        output.append([float(b) / 255.0 for b in h[:8]])
                    return output
                def embed_query(self, text):
                    return self.embed_documents([text])[0]
            self.embeddings = SimpleEmbeddings()
            self.model_name = "heuristic"
            print(f"✅ Heuristic embeddings initialized: {self.model_name}")
        
        # Initialize ChromaDB (disable telemetry/noise)
        print("💾 Initializing ChromaDB vector database...")
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
        # Suppress ChromaDB telemetry errors
        import logging
        logging.getLogger("chromadb").setLevel(logging.ERROR)
        try:
            self.chroma_client = chromadb.PersistentClient(path="./chroma_db", settings=Settings(anonymized_telemetry=False))
            print("✅ ChromaDB initialized successfully")
        except Exception as e:
            print(f"⚠️ ChromaDB initialization warning: {str(e)}")
            # Try to continue anyway
            self.chroma_client = chromadb.PersistentClient(path="./chroma_db", settings=Settings(anonymized_telemetry=False))
            print("✅ ChromaDB initialized (with warnings)")
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # Initialize vector store
        self.vectorstore = None
        self.collection_name = "requirements_documents"
        self.last_source = None  # track last processed filename for scoped queries
        # Global learned requirements collection (persists across runs via chroma path)
        self.global_collection_name = "global_requirements"
        try:
            # ensure collection exists
            _ = self.chroma_client.get_or_create_collection(self.global_collection_name)  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Initialize memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Create tools for search/summarize over RAG store
        self.tools = self._create_tools()
        # No LLM agent
        self.agent = None

        # Hybrid pipeline config (override via env)
        self.use_spacy = os.getenv("FLOWMIND_USE_SPACY", "1") == "1"
        self.use_reranker = os.getenv("FLOWMIND_USE_RERANKER", "1") == "1"
        self.use_llm_finalize = os.getenv("FLOWMIND_USE_LLM_FINALIZE", "0") == "1"
        self.ollama_model = os.getenv("FLOWMIND_OLLAMA_MODEL", "llama3:8b")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        
        # Self-learning configuration
        self.enable_self_learning = os.getenv("FLOWMIND_ENABLE_SELF_LEARNING", "1") == "1"
        print(f"🧠 Self-learning enabled: {self.enable_self_learning}")
        # User-specific collection names if user_id provided
        if user_id:
            self.learning_collection_name = f"learning_patterns_user_{user_id}"
            self.performance_collection_name = f"extraction_performance_user_{user_id}"
            print(f"👤 User-specific learning collections for user_id={user_id}")
        else:
            self.learning_collection_name = "learning_patterns"
            self.performance_collection_name = "extraction_performance"
            print("🌐 Using global learning collections")
        
        # Initialize learning components
        self._init_learning_system()
        
    # ---------------------- Self-Learning System ----------------------
    def _init_learning_system(self):
        """Initialize the self-learning system components."""
        try:
            # Create learning collections
            self.learning_collection = self.chroma_client.get_or_create_collection(
                name=self.learning_collection_name
            )
            self.performance_collection = self.chroma_client.get_or_create_collection(
                name=self.performance_collection_name
            )
            
            # Initialize learning data structures
            self.learned_patterns = {
                "functional": {"keywords": set(), "phrases": set(), "patterns": set()},
                "non_functional": {"keywords": set(), "phrases": set(), "patterns": set()},
                "user": {"keywords": set(), "phrases": set(), "patterns": set()},
                "system": {"keywords": set(), "phrases": set(), "patterns": set()},
                "business": {"keywords": set(), "phrases": set(), "patterns": set()},
                "features": {"keywords": set(), "phrases": set(), "patterns": set()}
            }
            
            # Performance tracking
            self.extraction_stats = {
                "total_documents": 0,
                "successful_extractions": 0,
                "failed_extractions": 0,
                "method_performance": {},
                "category_accuracy": {},
                "learning_iterations": 0,
                "average_quality_score": 0.0,
                "domain_contexts": {}
            }
            
            # Advanced features
            self.enable_quality_scoring = True
            self.enable_priority_detection = True
            self.enable_context_awareness = True
            
            # Load existing learned patterns
            self._load_learned_patterns()
            
            learned_count = len(self.learning_collection.get()['ids']) if hasattr(self, 'learning_collection') else 0
            print(f"📚 Loaded {learned_count} learned patterns from collection")
            print("🧠 Self-learning system initialized successfully")
            
        except Exception as e:
            print(f"⚠️ Failed to initialize learning system: {str(e)}")
            self.enable_self_learning = False
            # Initialize with defaults even if learning fails
            self.extraction_stats = {
                "total_documents": 0,
                "successful_extractions": 0,
                "failed_extractions": 0,
                "method_performance": {},
                "category_accuracy": {},
                "learning_iterations": 0,
                "average_quality_score": 0.0,
                "domain_contexts": {}
            }
            self.enable_quality_scoring = True
            self.enable_priority_detection = True
            self.enable_context_awareness = True
        
        print("✅ AI models and components initialized successfully")
        print(f"📊 Model: {self.model_name}, User ID: {self.user_id}, Self-learning: {self.enable_self_learning}")
    
    def _load_learned_patterns(self):
        """Load previously learned patterns from the learning collection."""
        try:
            if not self.enable_self_learning:
                return
                
            # Get all learned patterns
            results = self.learning_collection.get()
            
            if results and results.get("documents"):
                for doc, metadata in zip(results["documents"], results["metadatas"]):
                    category = metadata.get("category", "")
                    pattern_type = metadata.get("type", "")
                    pattern_value = doc
                    
                    if category in self.learned_patterns and pattern_type in self.learned_patterns[category]:
                        self.learned_patterns[category][pattern_type].add(pattern_value)
            
            total_loaded = sum(len(patterns['keywords']) + len(patterns['phrases']) + len(patterns['patterns']) for patterns in self.learned_patterns.values())
            if total_loaded > 0:
                print(f"📚 Loaded {total_loaded} learned patterns from previous runs")
                print(f"   - Keywords: {sum(len(p['keywords']) for p in self.learned_patterns.values())}")
                print(f"   - Phrases: {sum(len(p['phrases']) for p in self.learned_patterns.values())}")
                print(f"   - Patterns: {sum(len(p['patterns']) for p in self.learned_patterns.values())}")
            else:
                print(f"📚 No learned patterns found - starting fresh")
            
        except Exception as e:
            print(f"⚠️ Failed to load learned patterns: {str(e)}")
    
    def _save_learned_patterns(self):
        """Save learned patterns to the learning collection."""
        try:
            if not self.enable_self_learning:
                return
                
            # Get existing IDs to avoid duplicates
            existing_ids = set()
            try:
                existing_results = self.learning_collection.get()
                if existing_results and existing_results.get("ids"):
                    existing_ids = set(existing_results["ids"])
            except Exception:
                pass
            
            # Prepare new patterns (only those not already in collection)
            documents = []
            metadatas = []
            ids = []
            
            for category, patterns in self.learned_patterns.items():
                for pattern_type, pattern_set in patterns.items():
                    for pattern in pattern_set:
                        pattern_id = f"{category}_{pattern_type}_{hash(pattern)}"
                        # Only add if not already exists
                        if pattern_id not in existing_ids:
                            documents.append(pattern)
                            metadatas.append({"category": category, "type": pattern_type})
                            ids.append(pattern_id)
            
            # Use upsert to handle both new and existing patterns
            if documents:
                try:
                    # Try upsert first (ChromaDB 0.4+)
                    self.learning_collection.upsert(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                except AttributeError:
                    # Fallback to add if upsert not available
                    self.learning_collection.add(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                
        except Exception as e:
            print(f"⚠️ Failed to save learned patterns: {str(e)}")
    
    def _learn_from_extraction(self, text: str, extracted_sections: Dict[str, List[str]], filename: str):
        """Learn patterns and improve extraction from successful extractions."""
        try:
            if not self.enable_self_learning:
                return
                
            import re
            from collections import Counter
            
            # Track what we learned in this iteration
            new_keywords = 0
            new_phrases = 0
            new_patterns = 0
            
            # Analyze successful extractions to learn patterns
            for category, requirements in extracted_sections.items():
                if not requirements:
                    continue
                    
                category_key = category.lower().replace(" requirements", "").replace(" / stories", "").replace(" ", "_")
                if category_key not in self.learned_patterns:
                    continue
                
                # Learn keywords from successful requirements with frequency weighting
                for req in requirements:
                    words = re.findall(r'\b[a-zA-Z]{3,}\b', req.lower())
                    
                    # Learn important keywords (excluding common words)
                    common_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "up", "about", "into", "through", "during", "before", "after", "above", "below", "between", "among", "this", "that", "these", "those", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "shall"}
                    
                    important_words = [w for w in words if w not in common_words and len(w) > 3]
                    
                    # Add to learned keywords with priority for action words
                    for word in important_words:
                        if word not in self.learned_patterns[category_key]["keywords"]:
                            self.learned_patterns[category_key]["keywords"].add(word)
                            new_keywords += 1
                    
                    # Learn phrases (2-4 word combinations) - improved pattern
                    phrases = re.findall(r'\b(?:[a-zA-Z]+\s+){1,3}[a-zA-Z]+\b', req.lower())
                    for phrase in phrases:
                        if 2 <= len(phrase.split()) <= 4:
                            if phrase not in self.learned_patterns[category_key]["phrases"]:
                                self.learned_patterns[category_key]["phrases"].add(phrase)
                                new_phrases += 1
                    
                    # Learn enhanced sentence patterns with context
                    sentence_pattern = re.sub(r'\b[a-zA-Z]+\b', 'WORD', req.lower())
                    sentence_pattern = re.sub(r'\d+', 'NUM', sentence_pattern)
                    sentence_pattern = re.sub(r'[^\w\s]', '', sentence_pattern)  # Clean punctuation
                    if sentence_pattern not in self.learned_patterns[category_key]["patterns"]:
                        self.learned_patterns[category_key]["patterns"].add(sentence_pattern)
                        new_patterns += 1
                
                # Learn category-specific patterns from successful requirements
                category_patterns = self._extract_category_specific_patterns(category_key, requirements)
                for pattern_type, patterns in category_patterns.items():
                    for pattern in patterns:
                        if pattern not in self.learned_patterns[category_key][pattern_type]:
                            self.learned_patterns[category_key][pattern_type].add(pattern)
            
            # Learn from document context with improved analysis
            context_learned = self._learn_document_context(text, filename)
            
            # Update learning statistics with quality metrics
            self.extraction_stats["learning_iterations"] += 1
            
            # Track learning effectiveness
            total_learned = new_keywords + new_phrases + new_patterns
            if total_learned > 0:
                self.extraction_stats["last_learning_session"] = {
                    "keywords": new_keywords,
                    "phrases": new_phrases,
                    "patterns": new_patterns,
                    "total": total_learned,
                    "filename": filename
                }
                print(f"🧠 Learned {total_learned} new patterns ({new_keywords} keywords, {new_phrases} phrases, {new_patterns} patterns)")
            
            # Save learned patterns after each run for user-specific agents, or every 3 runs for global
            should_save = False
            if self.user_id is not None:
                # User-specific: save after every run
                should_save = True
            elif self.extraction_stats["learning_iterations"] % 3 == 0:
                # Global: save every 3 runs
                should_save = True
            
            if should_save:
                self._save_learned_patterns()
                user_msg = f" (user {self.user_id})" if self.user_id else ""
                print(f"💾 Saved learned patterns to persistent storage{user_msg}")
                
        except Exception as e:
            print(f"⚠️ Learning from extraction failed: {str(e)}")
    
    def _extract_category_specific_patterns(self, category_key: str, requirements: List[str]) -> Dict[str, set]:
        """Extract category-specific patterns from requirements."""
        import re
        patterns = {"keywords": set(), "phrases": set(), "patterns": set()}
        
        category_specific_keywords = {
            "functional": ["shall", "must", "will", "should", "enable", "allow", "provide", "support"],
            "non_functional": ["performance", "security", "reliability", "availability", "scalability"],
            "user": ["user", "persona", "role", "story", "as a", "i want"],
            "system": ["system", "api", "database", "server", "architecture"],
            "business": ["business", "policy", "compliance", "rule", "kpi", "roi"],
            "features": ["feature", "capability", "functionality", "supports", "allows"]
        }
        
        keywords = category_specific_keywords.get(category_key, [])
        for req in requirements:
            req_lower = req.lower()
            for keyword in keywords:
                if keyword in req_lower:
                    # Extract context around keyword (3 words before and after)
                    context = re.search(rf'\b(?:\w+\s+){{0,3}}{re.escape(keyword)}(?:\s+\w+){{0,3}}\b', req_lower)
                    if context:
                        patterns["phrases"].add(context.group().strip())
        
        return patterns
    
    def _learn_document_context(self, text: str, filename: str) -> Dict[str, int]:
        """Learn document-specific patterns and context with improved analysis."""
        try:
            import re
            from collections import Counter
            
            learned = {"keywords": 0, "phrases": 0, "patterns": 0}
            
            # Extract document-specific terminology (improved capitalization detection)
            words = re.findall(r'\b[A-Z][a-z]+\b', text)
            domain_terms = [w.lower() for w in words if len(w) > 4 and w.isalpha()]
            
            # Count term frequency to prioritize important terms
            term_counter = Counter(domain_terms)
            top_terms = [term for term, count in term_counter.most_common(20) if count >= 2]
            
            # Add top domain terms to all categories as important keywords
            for term in top_terms:
                for category in self.learned_patterns:
                    if term not in self.learned_patterns[category]["keywords"]:
                        self.learned_patterns[category]["keywords"].add(term)
                        learned["keywords"] += 1
            
            # Learn common patterns in this document type with better sentence segmentation
            sentences = re.split(r'[.!?]+', text)
            requirement_sentences = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if 20 < len(sentence) < 200:
                    sentence_lower = sentence.lower()
                    # Enhanced requirement detection
                    requirement_indicators = [
                        "shall", "must", "should", "will", "can", "enable", "allow", 
                        "provide", "support", "require", "need", "ensure", "implement"
                    ]
                    
                    if any(keyword in sentence_lower for keyword in requirement_indicators):
                        requirement_sentences.append(sentence)
            
            # Learn patterns from requirement sentences
            for sentence in requirement_sentences[:50]:  # Limit to prevent overload
                sentence_lower = sentence.lower()
                
                # Extract context around requirement keywords
                context_words = re.findall(r'\b[a-zA-Z]{4,}\b', sentence_lower)
                common_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "that", "this", "with", "when", "where"}
                
                important_words = [w for w in context_words if w not in common_words]
                
                # Add to all categories as cross-cutting knowledge
                for word in important_words[:10]:  # Limit per sentence
                    for category in self.learned_patterns:
                        if word not in self.learned_patterns[category]["keywords"]:
                            self.learned_patterns[category]["keywords"].add(word)
                            learned["keywords"] += 1
                
                # Learn requirement phrase patterns
                if "shall" in sentence_lower or "must" in sentence_lower:
                    # Extract verb phrases (e.g., "shall provide", "must enable")
                    verb_phrases = re.findall(r'\b(?:shall|must|should|will|can)\s+[a-zA-Z]+\b', sentence_lower)
                    for phrase in verb_phrases:
                        if phrase not in self.learned_patterns.get("functional", {}).get("phrases", set()):
                            if "functional" in self.learned_patterns:
                                self.learned_patterns["functional"]["phrases"].add(phrase)
                                learned["phrases"] += 1
            
            return learned
                                    
        except Exception as e:
            print(f"⚠️ Document context learning failed: {str(e)}")
            return {"keywords": 0, "phrases": 0, "patterns": 0}
    
    def _apply_learned_patterns(self, text: str) -> Dict[str, List[str]]:
        """Apply learned patterns to improve extraction accuracy with enhanced matching."""
        try:
            if not self.enable_self_learning:
                return {}
                
            import re
            
            enhanced_results = {}
            text_lower = text.lower()
            
            # Score matches by relevance
            for category, patterns in self.learned_patterns.items():
                if not any(patterns.values()):  # Skip if no learned patterns
                    continue
                    
                scored_matches = []
                seen_sentences = set()
                
                # Apply learned keywords with context scoring
                keyword_matches = 0
                for keyword in list(patterns["keywords"])[:100]:  # Limit to top 100 keywords
                    if keyword in text_lower:
                        keyword_matches += 1
                        # Find sentences containing this keyword
                        sentences = re.split(r'[.!?]+', text)
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if len(sentence) < 10:
                                continue
                            sentence_lower = sentence.lower()
                            if keyword in sentence_lower and sentence_lower not in seen_sentences:
                                seen_sentences.add(sentence_lower)
                                # Score by keyword relevance
                                score = 2.0 if keyword in sentence_lower[:50] else 1.0  # Higher score for early appearance
                                scored_matches.append((score, sentence))
                
                # Apply learned phrases with higher priority
                for phrase in list(patterns["phrases"])[:50]:  # Limit to top 50 phrases
                    if phrase in text_lower:
                        sentences = re.split(r'[.!?]+', text)
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if len(sentence) < 10:
                                continue
                            sentence_lower = sentence.lower()
                            if phrase in sentence_lower and sentence_lower not in seen_sentences:
                                seen_sentences.add(sentence_lower)
                                # Phrases get higher score as they're more specific
                                score = 3.0
                                scored_matches.append((score, sentence))
                
                # Apply learned patterns with context
                for pattern in list(patterns["patterns"])[:30]:  # Limit to top 30 patterns
                    # Convert pattern back to regex more robustly
                    regex_pattern = pattern.replace('WORD', r'\b[a-zA-Z]+\b').replace('NUM', r'\d+')
                    regex_pattern = re.escape(regex_pattern).replace('WORD', r'\b[a-zA-Z]+\b').replace('NUM', r'\d+')
                    try:
                        # Find all matches
                        found_matches = re.finditer(regex_pattern, text_lower, re.IGNORECASE)
                        for match in found_matches:
                            # Extract surrounding sentence
                            start = max(0, match.start() - 50)
                            end = min(len(text), match.end() + 50)
                            context = text[start:end]
                            # Extract full sentence
                            sentence_match = re.search(r'[^.!?]*[.!?]', context)
                            if sentence_match:
                                sentence = sentence_match.group().strip()
                                if len(sentence) >= 10:
                                    sentence_lower = sentence.lower()
                                    if sentence_lower not in seen_sentences:
                                        seen_sentences.add(sentence_lower)
                                        scored_matches.append((2.5, sentence))
                    except Exception:
                        continue
                
                # Sort by score and clean matches
                scored_matches.sort(key=lambda x: x[0], reverse=True)
                
                cleaned_matches = []
                seen_normalized = set()
                for score, match in scored_matches:
                    cleaned = self._normalize_line(match)
                    if cleaned and self._should_keep_line(cleaned):
                        normalized = re.sub(r'\s+', ' ', cleaned.lower().strip())
                        # Enhanced deduplication with similarity check
                        is_similar = False
                        for existing in seen_normalized:
                            # Simple similarity check
                            existing_words = set(existing.split())
                            match_words = set(normalized.split())
                            if len(existing_words) > 0 and len(match_words) > 0:
                                similarity = len(existing_words.intersection(match_words)) / len(existing_words.union(match_words))
                                if similarity > 0.75:  # 75% similarity threshold
                                    is_similar = True
                                    break
                        
                        if not is_similar and normalized not in seen_normalized:
                            seen_normalized.add(normalized)
                            cleaned_matches.append(cleaned)
                
                if cleaned_matches:
                    enhanced_results[category] = cleaned_matches[:15]  # Increased limit to top 15
                    if keyword_matches > 0:
                        print(f"📚 Applied {keyword_matches} learned keywords for {category}")
            
            return enhanced_results
            
        except Exception as e:
            print(f"⚠️ Applying learned patterns failed: {str(e)}")
            return {}
    
    def _update_performance_metrics(self, method_used: str, success: bool, categories_found: List[str]):
        """Update performance metrics for continuous improvement."""
        try:
            if not self.enable_self_learning:
                return
                
            # Update basic stats
            self.extraction_stats["total_documents"] += 1
            if success:
                self.extraction_stats["successful_extractions"] += 1
            else:
                self.extraction_stats["failed_extractions"] += 1
            
            # Update method performance
            if method_used not in self.extraction_stats["method_performance"]:
                self.extraction_stats["method_performance"][method_used] = {"success": 0, "total": 0}
            
            self.extraction_stats["method_performance"][method_used]["total"] += 1
            if success:
                self.extraction_stats["method_performance"][method_used]["success"] += 1
            
            # Update category accuracy
            for category in categories_found:
                if category not in self.extraction_stats["category_accuracy"]:
                    self.extraction_stats["category_accuracy"][category] = 0
                self.extraction_stats["category_accuracy"][category] += 1
            
            # Save performance metrics periodically
            if self.extraction_stats["total_documents"] % 10 == 0:
                self._save_performance_metrics()
                
        except Exception as e:
            print(f"⚠️ Performance metrics update failed: {str(e)}")
    
    def _save_performance_metrics(self):
        """Save performance metrics to the performance collection."""
        try:
            if not self.enable_self_learning:
                return
                
            # Clear existing metrics
            try:
                self.performance_collection.delete()
                self.performance_collection = self.chroma_client.get_or_create_collection(
                    name=self.performance_collection_name
                )
            except Exception:
                pass
            
            # Save current metrics
            import json
            metrics_json = json.dumps(self.extraction_stats, indent=2)
            
            self.performance_collection.add(
                documents=[metrics_json],
                metadatas=[{"type": "performance_metrics", "timestamp": str(time.time())}],
                ids=["performance_metrics"]
            )
            
        except Exception as e:
            print(f"⚠️ Failed to save performance metrics: {str(e)}")
    
    def get_learning_status(self) -> Dict[str, Any]:
        """Get current learning status and statistics."""
        try:
            total_patterns = sum(
                len(patterns["keywords"]) + len(patterns["phrases"]) + len(patterns["patterns"])
                for patterns in self.learned_patterns.values()
            )
            
            method_success_rates = {}
            for method, stats in self.extraction_stats["method_performance"].items():
                if stats["total"] > 0:
                    method_success_rates[method] = stats["success"] / stats["total"]
            
            return {
                "learning_enabled": self.enable_self_learning,
                "total_learned_patterns": total_patterns,
                "learning_iterations": self.extraction_stats["learning_iterations"],
                "total_documents_processed": self.extraction_stats["total_documents"],
                "success_rate": self.extraction_stats["successful_extractions"] / max(1, self.extraction_stats["total_documents"]),
                "method_success_rates": method_success_rates,
                "category_accuracy": self.extraction_stats["category_accuracy"],
                "patterns_by_category": {
                    category: {
                        "keywords": len(patterns["keywords"]),
                        "phrases": len(patterns["phrases"]),
                        "patterns": len(patterns["patterns"])
                    }
                    for category, patterns in self.learned_patterns.items()
                },
                "last_learning_session": self.extraction_stats.get("last_learning_session", {})
            }
            
        except Exception as e:
            return {"error": f"Failed to get learning status: {str(e)}"}
    
    def _format_learned_results(self, learned_results: Dict[str, List[str]]) -> str:
        """Format learned results into a readable string."""
        try:
            if not learned_results:
                return ""
            
            formatted_sections = []
            
            for category, requirements in learned_results.items():
                if requirements:
                    formatted_sections.append(f"\n## {category.replace('_', ' ').title()} Requirements")
                    for i, req in enumerate(requirements[:10], 1):  # Limit to top 10
                        formatted_sections.append(f"{i}. {req}")
            
            return "\n".join(formatted_sections)
            
        except Exception as e:
            return f"Error formatting learned results: {str(e)}"
    
    def _parse_response_to_sections(self, response_text: str) -> Dict[str, List[str]]:
        """Parse formatted response text into sections for learning."""
        try:
            sections = {}
            current_section = None
            current_items = []
            
            lines = response_text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this is a section heading (ends with colon)
                if line.endswith(":") and not line.startswith("-"):
                    # Save previous section
                    if current_section and current_items:
                        sections[current_section] = current_items
                    
                    # Start new section
                    current_section = line.rstrip(":").lower().replace(" ", "_")
                    # Normalize section name
                    current_section = current_section.replace("_requirements", "").replace("_/", "_").replace("_stories", "_stories")
                    current_items = []
                # Check if this is a bullet point
                elif line.startswith("- "):
                    requirement = line[2:].strip()
                    if requirement and requirement.lower() != "(none)":
                        current_items.append(requirement)
            
            # Save last section
            if current_section and current_items:
                sections[current_section] = current_items
            
            return sections
            
        except Exception as e:
            print(f"⚠️ Error parsing response to sections: {str(e)}")
            return {}
        
    # ---------------------- Formatting Helpers ----------------------
    def _normalize_line(self, line: str) -> str:
        """Enhanced normalization for better requirement extraction."""
        if not line:
            return ""
        
        s = line.strip()
        
        # Remove common bullet symbols and numbering patterns
        s = re.sub(r"^[\-•●\u2022\u25CF\u25E6\s]*", "", s)
        s = re.sub(r"^\d+[\.\)]\s*", "", s)  # Handle both "1." and "1)" patterns
        s = re.sub(r"^[a-zA-Z][\.\)]\s*", "", s)  # Handle "a." and "a)" patterns
        s = re.sub(r"^[ivx]+[\.\)]\s*", "", s, flags=re.IGNORECASE)  # Handle roman numerals
        
        # Normalize whitespace and special characters
        s = re.sub(r"\s+", " ", s)
        s = s.replace("→", "->").replace("⇒", "->").replace("→", "->")
        s = s.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
        
        # Clean up common artifacts
        s = re.sub(r"^\s*[:\-]\s*", "", s)  # Remove leading colons and dashes
        s = re.sub(r"\s*[:\-]\s*$", "", s)  # Remove trailing colons and dashes
        
        # Normalize requirement keywords for consistency
        s = re.sub(r"\b(must|shall|should|will|can|could|may|might)\b", lambda m: m.group(1).lower(), s, flags=re.IGNORECASE)
        
        # Remove excessive punctuation but preserve sentence structure
        s = re.sub(r"\.{2,}", ".", s)  # Multiple periods to single
        s = re.sub(r"!{2,}", "!", s)   # Multiple exclamations to single
        s = re.sub(r"\?{2,}", "?", s)  # Multiple questions to single
        
        # Strip trailing periods for uniformity (but keep internal punctuation)
        s = re.sub(r"\s*\.$", "", s)
        
        return s.strip()

    def _should_keep_line(self, line: str) -> bool:
        """Enhanced filtering for more accurate requirement extraction."""
        s = (line or "").strip().lower()
        if not s:
            return False
        
        # Enhanced heading detection with more patterns
        # NOTE: Don't filter section headers that end with ":" - they're used in output formatting
        heading_patterns = (
            "introduction", "submission guidelines", "exercises", "exercise ",
            "step ", "follow these steps", "your jenkins pipeline should:", 
            "table of contents", "contents",
            "abstract", "summary", "conclusion", "references", "bibliography",
            "appendix", "glossary", "index", "acknowledgments", "acknowledgements"
        )
        if any(s.startswith(h) for h in heading_patterns):
            return False
            
        # Enhanced metadata detection
        metadata_patterns = (
            "by:", "supervised by", "thank you", "copyright", "all rights reserved",
            "page", "figure", "table", "section", "chapter", "part"
        )
        if any(pattern in s for pattern in metadata_patterns):
            return False
            
        # Enhanced URL and link detection
        if any(pattern in s for pattern in ("http://", "https://", "www.", "ftp://", "mailto:")):
            return False
            
        # Enhanced punctuation-only detection
        if s in {"-", "--", "—", "*", ":", ".", "!", "?", "...", "…"}:
            return False
            
        # Enhanced colon-heavy content detection (likely headings or lists)
        if s.count(":") >= 2 and len(s.split()) < 10:
            return False
            
        # Enhanced actionable keyword detection
        strong_actionable = (
            "must", "shall", "should", "will", "ensure", "trigger", "push", "build",
            "run", "install", "create", "implement", "verify", "pull", "checkout",
            "tag", "merge", "webhook", "docker", "jenkins", "branch", "database",
            "frontend", "backend", "api", "endpoint", "service", "component",
            "module", "function", "feature", "capability", "requirement", "constraint"
        )
        
        # Enhanced user story patterns
        user_story_patterns = (
            "as a", "as an", "as the", "i want", "i need", "i should", "i can",
            "so that", "in order to", "user can", "user should", "user must"
        )
        
        # Enhanced technical patterns
        technical_patterns = (
            "system shall", "system must", "system should", "application shall",
            "application must", "application should", "software shall", "software must",
            "software should", "platform shall", "platform must", "platform should"
        )
        
        # Check for strong requirement indicators
        if any(k in s for k in strong_actionable):
            return True
        if any(pattern in s for pattern in user_story_patterns):
            return True
        if any(pattern in s for pattern in technical_patterns):
            return True
            
        # Enhanced quality attribute detection
        quality_attributes = (
            "performance", "latency", "throughput", "availability", "security",
            "encryption", "usability", "reliability", "scalability", "maintainability",
            "portability", "compatibility", "accessibility", "efficiency", "robustness"
        )
        if any(attr in s for attr in quality_attributes):
            return True
            
        # Enhanced business rule detection
        business_patterns = (
            "policy", "compliance", "regulation", "standard", "guideline",
            "kpi", "roi", "metric", "measurement", "threshold", "limit",
            "constraint", "restriction", "rule", "business rule"
        )
        if any(pattern in s for pattern in business_patterns):
            return True
            
        # Enhanced length and content quality checks
        if len(s) < 10:  # Too short to be meaningful
            return False
        if len(s) > 500:  # Too long, likely not a single requirement
            return False
            
        # Enhanced sentence structure detection
        if s.count(".") > 3:  # Multiple sentences, likely descriptive text
            return False
            
        # Enhanced verb detection for actionable content
        action_verbs = (
            "enable", "allow", "provide", "support", "include", "exclude",
            "generate", "process", "handle", "manage", "control", "monitor",
            "track", "log", "report", "notify", "alert", "validate", "authenticate"
        )
        if any(verb in s for verb in action_verbs):
            return True
            
        # Keep moderately informative statements with good structure
        return len(s) > 15 and len(s.split()) >= 3

    def _format_sections(self, sections: Dict[str, List[str]]) -> str:
        """Format sections into a user-friendly, deduplicated bullet list per section with quality indicators."""
        global_seen = set()
        parts: List[str] = []
        total_quality = 0
        total_count = 0
        
        for title, items in sections.items():
            cleaned: List[str] = []
            req_data: List[tuple] = []  # (line, quality_score)
            
            for item in items or []:
                line = self._normalize_line(item)
                if not self._should_keep_line(line):
                    continue
                key = re.sub(r"[^a-z0-9 ]+", "", line.lower())
                if key in global_seen:
                    continue
                global_seen.add(key)
                
                # Calculate quality score
                quality_score = self._score_requirement_quality(line) if self.enable_quality_scoring else 0
                req_data.append((line, quality_score))
                total_quality += quality_score
                total_count += 1
            
            # Enhanced sorting: first by mandatory keywords, then by quality, then by length
            def enhanced_sort_key(x: tuple) -> tuple:
                line, quality = x
                xl = line.lower()
                priority = 0
                
                # Critical/mandatory requirements first
                if any(w in xl for w in (" must ", " shall ", " critical ")):
                    priority = -4
                elif " should " in xl:
                    priority = -3
                elif xl.startswith("ensure") or xl.startswith("implement"):
                    priority = -2
                elif any(w in xl for w in (" can ", " may ")):
                    priority = -1
                
                # Secondary sort by quality (higher quality first within same priority)
                return (priority, -quality, len(line))
            
            req_data.sort(key=enhanced_sort_key)
            
            if req_data:
                bullet_lines = []
                for line, quality in req_data:
                    # Add quality indicator for high/low quality requirements
                    if self.enable_quality_scoring and quality > 0:
                        if quality >= 80:
                            indicator = "✅ "  # High quality
                        elif quality >= 60:
                            indicator = "⚠️  "  # Medium quality
                        elif quality < 50:
                            indicator = "❌ "  # Low quality - needs review
                        else:
                            indicator = ""
                    else:
                        indicator = ""
                    
                    bullet_lines.append(f"- {indicator}{line}")
                
                # Add quality summary for the section
                avg_quality = sum(q for _, q in req_data) / len(req_data) if req_data else 0
                quality_summary = ""
                if self.enable_quality_scoring and avg_quality > 0:
                    quality_summary = f" (Avg Quality: {avg_quality:.0f}/100)"
                
                parts.append(f"{title} ({len(bullet_lines)} items{quality_summary}):\n" + "\n".join(bullet_lines))
            else:
                parts.append(f"{title}:\n(none)")
        
        # Update global statistics
        if total_count > 0:
            self.extraction_stats["average_quality_score"] = total_quality / total_count
        
        return "\n\n".join(parts)

    # ---------------------- Learning ----------------------
    def _learn_from_results(self, filename: str, sections: Dict[str, List[str]]) -> None:
        """Persist extracted requirement bullets into a global embeddings collection for future boosting."""
        try:
            from langchain.schema import Document as _Doc
            docs: List[_Doc] = []
            for section_name, items in sections.items():
                for item in items or []:
                    norm = self._normalize_line(item)
                    if not self._should_keep_line(norm):
                        continue
                    docs.append(_Doc(page_content=norm, metadata={"source": filename, "section": section_name}))
            if not docs:
                return
            # Upsert into a stable global collection
            Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                collection_name=self.global_collection_name,
                client=self.chroma_client
            )
        except Exception:
            # Learning should be best-effort; ignore failures
            pass

    # ---------------------- Enrichment Steps ----------------------
    def _spacy_filter(self, sentences: List[str]) -> List[bool]:
        """Optional spaCy filter to keep imperative/actionable sentences. Returns mask."""
        if not self.use_spacy:
            return [True] * len(sentences)
        try:
            import spacy  # type: ignore
            try:
                nlp = spacy.load("en_core_web_sm")
            except Exception:
                return [True] * len(sentences)
            mask: List[bool] = []
            for s in sentences:
                if len(s) < 8:
                    mask.append(False)
                    continue
                doc = nlp(s)
                # Keep if starts with VERB or contains modal (shall/must/should)
                starts_with_verb = any(t.pos_ == "VERB" for t in doc[:3])
                has_modal = any(t.lemma_.lower() in ("shall", "must", "should") for t in doc)
                mask.append(bool(starts_with_verb or has_modal))
            return mask
        except Exception:
            return [True] * len(sentences)

    def _near_duplicate_filter(self, sentences: List[str], threshold: float = 0.92) -> List[str]:
        """Remove near-duplicate sentences using embedding cosine similarity."""
        if len(sentences) <= 1:
            return sentences
        try:
            import math
            vecs = self.embeddings.embed_documents(sentences)
            kept: List[int] = []
            for i, v in enumerate(vecs):
                is_dup = False
                for ki in kept:
                    u = vecs[ki]
                    dot = sum(x*y for x, y in zip(v, u))
                    nv = math.sqrt(sum(x*x for x in v)) or 1.0
                    nu = math.sqrt(sum(x*x for x in u)) or 1.0
                    sim = dot / (nv * nu)
                    if sim >= threshold:
                        is_dup = True
                        break
                if not is_dup:
                    kept.append(i)
            return [sentences[i] for i in kept]
        except Exception:
            # Fallback to exact-key dedup only
            seen = set()
            out = []
            for s in sentences:
                k = s.strip().lower()
                if k in seen:
                    continue
                seen.add(k)
                out.append(s)
            return out

    def _rerank(self, query: str, candidates: List[str], top_k: int = 10) -> List[str]:
        """Optional cross-encoder reranking of candidates; fallback to identity order."""
        if not self.use_reranker or len(candidates) <= 2:
            return candidates[:top_k]
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            model = os.getenv("FLOWMIND_RERANKER_MODEL", "BAAI/bge-reranker-base")
            ce = CrossEncoder(model, max_length=512)
            pairs = [(query, c) for c in candidates]
            scores = ce.predict(pairs)
            ranked = sorted(zip(candidates, scores), key=lambda t: t[1], reverse=True)
            return [c for c, _ in ranked[:top_k]]
        except Exception:
            return candidates[:top_k]

    def _llm_finalize(self, section_text: str) -> str:
        """Optional LLM polishing via Ollama (local) or OpenRouter; fallback to input."""
        if not self.use_llm_finalize:
            return section_text
        prompt = (
            "Rewrite the following extracted requirements into concise, non-duplicated bullet points, "
            "organized strictly under these headings: Functional Requirements, Non-Functional Requirements, "
            "User Requirements / Stories, System Requirements, Business Requirements, Features. "
            "Keep only actionable, requirement-like content. Do not invent details.\n\n" + section_text
        )
        # Try Ollama first
        try:
            import requests  # type: ignore
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": self.ollama_model, "prompt": prompt, "stream": False},
                timeout=15,
            )
            if resp.ok:
                data = resp.json()
                out = data.get("response") or data.get("output") or ""
                return out.strip() or section_text
        except Exception:
            pass
        # Try OpenRouter if key present
        if self.openrouter_key:
            try:
                import requests  # type: ignore
                headers = {
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                }
                body = {
                    "model": os.getenv("FLOWMIND_OPENROUTER_MODEL", "meta-llama/llama-3.1-70b-instruct"),
                    "messages": [{"role": "user", "content": prompt}],
                }
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body, timeout=20)
                if resp.ok:
                    data = resp.json()
                    choice = (data.get("choices") or [{}])[0]
                    out = ((choice.get("message") or {}).get("content") or "").strip()
                    return out or section_text
            except Exception:
                pass
        return section_text

    def _create_tools(self) -> List[Tool]:
        """Create tools for the agent."""
        
        def search_requirements(query: str) -> str:
            """Search for requirements and features in the document collection."""
            if self.vectorstore is None:
                return "No documents have been processed yet. Please upload and process a document first."
            
            try:
                docs = self.vectorstore.similarity_search(query, k=5)
                if not docs:
                    return "No relevant requirements found for the query."
                
                results = []
                for i, doc in enumerate(docs, 1):
                    results.append(f"Result {i}:\n{doc.page_content}\n---")
                
                return "\n".join(results)
            except Exception as e:
                return f"Error searching requirements: {str(e)}"
        
        def extract_specific_requirements(req_type: str) -> str:
            """Extract specific types of requirements (functional, non-functional, etc.)."""
            if self.vectorstore is None:
                return "No documents have been processed yet."
            
            try:
                # Search for specific requirement types
                search_queries = {
                    "functional": "functional requirements features capabilities system must do",
                    "non-functional": "non-functional requirements performance security usability reliability",
                    "user": "user requirements user stories user needs user interface",
                    "system": "system requirements technical requirements architecture",
                    "business": "business requirements business rules business logic"
                }
                
                query = search_queries.get(req_type.lower(), req_type)
                docs = self.vectorstore.similarity_search(query, k=10)
                
                if not docs:
                    return f"No {req_type} requirements found."
                
                results = []
                for i, doc in enumerate(docs, 1):
                    results.append(f"{req_type.title()} Requirement {i}:\n{doc.page_content}\n---")
                
                return "\n".join(results)
            except Exception as e:
                return f"Error extracting {req_type} requirements: {str(e)}"
        
        def summarize_document() -> str:
            """Provide a summary of all processed documents."""
            if self.vectorstore is None:
                return "No documents have been processed yet."
            
            try:
                # Get all documents
                docs = self.vectorstore.similarity_search("", k=20)
                if not docs:
                    return "No documents found."
                
                # Create a summary
                all_text = "\n".join([doc.page_content for doc in docs])
                
                summary_prompt = f"""
                Please provide a comprehensive summary of the following document content, focusing on:
                1. Main purpose and objectives
                2. Key features and functionalities
                3. Important requirements
                4. Technical specifications
                5. User needs and expectations
                
                Document content:
                {all_text[:3000]}...
                """
                
                # Heuristic summary without LLM
                return (all_text[:1000] + ("..." if len(all_text) > 1000 else ""))
            except Exception as e:
                return f"Error creating summary: {str(e)}"
        
        return [
            Tool(
                name="search_requirements",
                description="Search for specific requirements, features, or capabilities in the processed documents",
                func=search_requirements
            ),
            Tool(
                name="extract_specific_requirements",
                description="Extract specific types of requirements: functional, non-functional, user, system, or business requirements",
                func=extract_specific_requirements
            ),
            Tool(
                name="summarize_document",
                description="Provide a comprehensive summary of all processed documents",
                func=summarize_document
            )
        ]
    
    def _create_agent(self) -> AgentExecutor:
        """Create the agent with tools and prompt."""
        
        prompt = PromptTemplate(
            template="""You are an expert requirements analyst and software engineer. Your task is to analyze documents and extract features, requirements, and specifications.

You have access to the following tools:
{tools}

When analyzing documents, focus on:
1. Functional requirements (what the system must do)
2. Non-functional requirements (performance, security, usability)
3. User requirements and user stories
4. System requirements and technical specifications
5. Business requirements and rules
6. Features and capabilities
7. Constraints and limitations

Always provide clear, structured responses with specific examples from the documents. If you cannot find specific information, clearly state what is missing.

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}""",
            input_variables=["input", "agent_scratchpad", "tool_names", "tools"]
        )
        
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
    
    def process_document(self, text: str, filename: str) -> Dict[str, Any]:
        """Process a document and add it to the vector store."""
        try:
            # Split the text into chunks
            chunks = self.text_splitter.split_text(text)
            
            # Create documents
            documents = [
                Document(
                    page_content=chunk,
                    metadata={"source": filename, "chunk_id": i}
                )
                for i, chunk in enumerate(chunks)
            ]
            
            # Use a fresh, per-file collection to avoid cross-document bleed
            safe_name = "req_" + str(abs(hash(filename)) % (10**10))
            self.collection_name = safe_name
            self.vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                collection_name=self.collection_name,
                client=self.chroma_client
            )
            self.last_source = filename
            
            return {
                "status": "success",
                "message": f"Document '{filename}' processed successfully",
                "chunks_created": len(chunks),
                "total_chunks": len(documents)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing document: {str(e)}"
            }
    
    def _reclassify_and_deduplicate_all(self, initial_categories: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Reclassify all requirements to their correct categories."""
        all_reqs_with_category = []
        
        for category, reqs in initial_categories.items():
            for req in reqs:
                # Reclassify each requirement
                correct_category = self._classify_requirement_improved(req)
                all_reqs_with_category.append((req, correct_category))
        
        # Build reclassified dict
        result = {
            'functional': [],
            'non_functional': [],
            'user': [],
            'business': [],
            'system': [],
            'features': []
        }
        
        for req, category in all_reqs_with_category:
            if category in result:
                result[category].append(req)
        
        return result

    def _cross_category_deduplicate(self, categorized: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Remove duplicates across ALL categories using advanced similarity detection."""
        import re
        
        # Collect all requirements with normalized versions
        all_reqs = []  # (original, normalized, category)
        
        for category, reqs in categorized.items():
            for req in reqs:
                normalized = re.sub(r'\s+', ' ', req.strip().lower())
                normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
                all_reqs.append((req, normalized, category))
        
        # Track what we've seen
        seen_normalized = set()
        seen_core_keys = set()
        kept_reqs = []
        
        for original, normalized, category in all_reqs:
            # Check 1: Exact match
            if normalized in seen_normalized:
                continue
            
            # Check 2: Core content match (remove common prefixes)
            core_text = normalized
            for prefix in ['bot must', 'system must', 'application must', 'bot shall', 
                           'system shall', 'must', 'shall', 'should', 'will']:
                if core_text.startswith(prefix + ' '):
                    core_text = core_text[len(prefix)+1:].strip()
                    break
            
            # Create key from core content words
            words = core_text.split()
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
                          'for', 'of', 'with', 'by', 'from', 'as', 'is', 'are'}
            content_words = [w for w in words if w not in stop_words and len(w) > 2]
            core_key = ' '.join(sorted(content_words[:10]))
            
            if core_key in seen_core_keys and len(core_key) > 15:
                continue
            
            # Check 3: Similarity with existing kept requirements
            is_duplicate = False
            current_words = set(normalized.split())
            
            for _, kept_normalized, _ in kept_reqs:
                kept_words = set(kept_normalized.split())
                
                if len(current_words) > 3 and len(kept_words) > 3:
                    intersection = len(current_words.intersection(kept_words))
                    union = len(current_words.union(kept_words))
                    similarity = intersection / union if union > 0 else 0
                    
                    # Jaccard similarity threshold
                    if similarity >= 0.75:
                        is_duplicate = True
                        break
                    
                    # Containment check (one is mostly contained in the other)
                    containment = intersection / min(len(current_words), len(kept_words))
                    if containment >= 0.85:
                        is_duplicate = True
                        break
            
            if is_duplicate:
                continue
            
            # Keep this requirement
            seen_normalized.add(normalized)
            if core_key and len(core_key) > 15:
                seen_core_keys.add(core_key)
            kept_reqs.append((original, normalized, category))
        
        # Rebuild categorized dict
        result = {cat: [] for cat in categorized.keys()}
        for original, _, category in kept_reqs:
            if category in result:
                result[category].append(original)
        
        return result

    def _is_valid_requirement(self, sentence: str) -> bool:
        """Filter out non-requirements like dates, project info, metadata."""
        normalized = sentence.lower().strip()
        
        # Minimum length check
        if len(normalized) < 15:
            return False
        
        # Exclude pure metadata, headers, dates
        import re
        exclude_patterns = [
            r'^\d+\.?\s*$',  # Just numbers
            r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',  # Starts with month
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # Dates
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
            r'timeline.*(jan|feb|mar|apr|may|june|july|aug|sep|oct|nov|dec|\d{4})',
            r'expected.*\d{4}',  # Expected dates
            r'delivery.*\d{4}',  # Delivery dates  
            r'due.*\d{4}',  # Due dates
            r'demo.*\d{4}',  # Demo dates
            r'^(page|section|chapter|figure|table|appendix)\s+\d+',  # Document structure
            r'^(version|revision|date|author|title)',  # Document metadata
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, normalized):
                return False
        
        # Require some requirement-like indicators
        requirement_indicators = [
            'must', 'shall', 'should', 'will', 'can', 'may',
            'enable', 'allow', 'provide', 'support', 'include',
            'process', 'handle', 'manage', 'generate', 'validate',
            'bot', 'system', 'application', 'platform', 'user',
        ]
        
        has_indicator = any(indicator in normalized for indicator in requirement_indicators)
        if not has_indicator:
            return False
        
        return True

    def _score_requirement_quality(self, requirement: str) -> float:
        """
        Advanced quality scoring for requirements.
        Returns overall quality score (0-100).
        """
        normalized = requirement.lower().strip()
        words = normalized.split()
        word_count = len(words)
        
        score = 50  # Base score
        
        # Length scoring (prefer 5-30 words)
        if 5 <= word_count <= 30:
            score += 15
        elif word_count < 5:
            score -= 20
        elif word_count > 50:
            score -= 10
        
        # Clear action verbs boost
        clear_verbs = ['must', 'shall', 'will', 'calculate', 'fetch', 'collect', 
                       'book', 'reserve', 'charge', 'process', 'validate', 'provide']
        score += min(20, sum(3 for v in clear_verbs if v in normalized))
        
        # Specificity boost (has API, numbers, specific terms)
        if any(term in normalized for term in ['api', 'using', 'via', 'through']):
            score += 10
        if re.search(r'\d+', normalized):
            score += 5
        
        # Vague terms penalty
        vague_terms = ['somehow', 'maybe', 'probably', 'might', 'approximately', 'user-friendly', 'fast', 'good']
        score -= sum(5 for term in vague_terms if term in normalized)
        
        # Multiple 'and' penalty (compound requirements)
        score -= min(15, normalized.count(' and ') * 5)
        
        # Has clear actor bonus
        if any(actor in normalized for actor in ['bot', 'system', 'user', 'application']):
            score += 10
        
        return max(0, min(100, score))

    def _detect_domain_context(self, text: str) -> str:
        """Detect the domain/context of the requirements."""
        normalized = text.lower()
        
        # Count domain indicators
        domains = {
            'booking_system': ['book', 'reservation', 'appointment', 'schedule', 'slot', 'availability'],
            'e_commerce': ['payment', 'checkout', 'cart', 'product', 'order', 'purchase'],
            'api_service': ['api', 'endpoint', 'rest', 'request', 'response', 'json'],
            'web_app': ['web', 'browser', 'http', 'html', 'frontend', 'backend'],
            'security': ['security', 'encryption', 'authentication', 'authorization', 'access']
        }
        
        domain_scores = {}
        for domain, keywords in domains.items():
            domain_scores[domain] = sum(1 for kw in keywords if kw in normalized)
        
        # Return domain with highest score, or 'general'
        if max(domain_scores.values()) > 0:
            return max(domain_scores, key=domain_scores.get)
        return 'general'

    def _classify_requirement_improved(self, sentence: str, context: str = '') -> str:
        """
        Improved classification with context awareness and domain knowledge.
        """
        normalized = sentence.lower().strip()
        import re
        
        # Detect domain for context-aware classification
        domain = self._detect_domain_context(sentence + ' ' + context)
        
        # PRIORITY 1: User Stories (highest specificity)
        user_story_patterns = [
            r'as\s+(a|an|the)\s+\w+',
            r'i\s+(want|need|should|can|will)',
            r'so\s+that',
            r'user\s+story',
        ]
        
        if any(re.search(pattern, normalized) for pattern in user_story_patterns):
            return 'user'
        
        # PRIORITY 2: Non-Functional (quality attributes ONLY)
        nfr_indicators = [
            'performance', 'latency', 'throughput', 'response time',
            'security', 'encryption', 'authentication', 
            'reliability', 'availability', 'uptime', 'downtime',
            'scalability', 'scalable', 'concurrent users',
            'usability', 'user-friendly', 'accessible',
            'maintainability', 'portability', 'compatibility',
        ]
        
        nfr_patterns = [
            r'within\s+\d+\s*(ms|millisecond|second|minute)',
            r'\d+%\s+(uptime|availability)',
            r'requests\s+per\s+second',
            r'concurrent\s+users',
        ]
        
        # Check for NFR signals
        nfr_count = sum(1 for indicator in nfr_indicators if indicator in normalized)
        has_nfr_pattern = any(re.search(pattern, normalized) for pattern in nfr_patterns)
        
        # Important: Payment, deposits, calculations are FUNCTIONAL, not NFR
        # Domain-aware functional indicators
        functional_business_keywords = [
            'collect', 'charge', 'payment', 'deposit', 'invoice',
            'calculate', 'compute', 'fetch', 'gather', 'book', 'reserve',
            'assign', 'schedule', 'using', 'api', 'maps', 'process order',
        ]
        
        # Add domain-specific functional keywords
        if domain == 'booking_system':
            functional_business_keywords.extend(['availability', 'slot', 'calendar'])
        elif domain == 'e_commerce':
            functional_business_keywords.extend(['checkout', 'cart', 'product'])
        
        has_functional = any(keyword in normalized for keyword in functional_business_keywords)
        
        # NFR only if it has NFR signals AND NO functional keywords
        if (nfr_count >= 2 or has_nfr_pattern) and not has_functional:
            return 'non_functional'
        
        # PRIORITY 3: Business Rules
        business_indicators = [
            'business rule', 'policy', 'regulation', 'compliance',
            'approval', 'stakeholder', 'kpi', 'roi',
        ]
        
        if any(indicator in normalized for indicator in business_indicators):
            return 'business'
        
        # Default: Functional (most action-oriented requirements)
        return 'functional'

    def _heuristic_extract(self, text: str) -> Dict[str, Any]:
        """Enhanced heuristic extraction with improved accuracy and classification."""
        try:
            # Enhanced text preprocessing
            content = (text or "").strip()
            if not content:
                return {"status": "success", "response": "No content to analyze."}
            
            # Split into sentences for better analysis
            sentences = re.split(r'(?<=[.!?])\s+', content)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # STEP 1: Filter out non-requirements early
            sentences = [s for s in sentences if self._is_valid_requirement(s)]
            
            # Enhanced keyword patterns with better specificity
            patterns = {
                "functional": {
                    "strong": [
                        "shall", "must", "should", "will", "system shall", "application shall",
                        "software shall", "platform shall", "user shall", "system must",
                        "application must", "software must", "platform must", "user must"
                    ],
                    "moderate": [
                        "enable", "allow", "provide", "support", "include", "exclude",
                        "generate", "process", "handle", "manage", "control", "monitor",
                        "track", "log", "report", "notify", "alert", "validate", "authenticate",
                        "user can", "user should", "user will", "system can", "system should",
                        "application can", "application should", "software can", "software should"
                    ],
                    "weak": [
                        "capability", "functionality", "feature", "function", "operation",
                        "action", "task", "workflow", "process", "procedure"
                    ]
                },
                "non_functional": {
                    "strong": [
                        "performance", "latency", "throughput", "availability", "security",
                        "encryption", "usability", "reliability", "scalability", "maintainability",
                        "portability", "compatibility", "accessibility", "efficiency", "robustness",
                        "response time", "uptime", "downtime", "bandwidth", "memory usage",
                        "cpu usage", "storage capacity", "load capacity", "concurrent users"
                    ],
                    "moderate": [
                        "quality", "standard", "requirement", "constraint", "limit",
                        "threshold", "metric", "measurement", "benchmark", "criteria"
                    ],
                    "weak": [
                        "fast", "slow", "quick", "efficient", "stable", "secure",
                        "user-friendly", "intuitive", "responsive", "reliable"
                    ]
                },
                "user": {
                    "strong": [
                        "as a", "as an", "as the", "i want", "i need", "i should",
                        "i can", "so that", "in order to", "user story", "persona",
                        "role", "actor", "stakeholder"
                    ],
                    "moderate": [
                        "user experience", "user interface", "user interaction",
                        "user workflow", "user journey", "user needs", "user goals"
                    ],
                    "weak": [
                        "user", "customer", "client", "end-user", "operator"
                    ]
                },
                "system": {
                    "strong": [
                        "architecture", "server", "database", "api", "endpoint",
                        "service", "component", "module", "framework", "library",
                        "infrastructure", "deployment", "configuration", "integration"
                    ],
                    "moderate": [
                        "technical", "system", "application", "software", "platform",
                        "environment", "technology", "implementation", "development"
                    ],
                    "weak": [
                        "code", "program", "application", "system", "tool"
                    ]
                },
                "business": {
                    "strong": [
                        "business rule", "policy", "compliance", "regulation", "standard",
                        "guideline", "kpi", "roi", "metric", "measurement", "threshold",
                        "limit", "constraint", "restriction", "rule", "procedure"
                    ],
                    "moderate": [
                        "business", "stakeholder", "requirement", "objective", "goal",
                        "strategy", "process", "workflow", "approval", "authorization"
                    ],
                    "weak": [
                        "company", "organization", "enterprise", "corporate"
                    ]
                },
                "features": {
                    "strong": [
                        "feature", "capability", "functionality", "supports", "allows",
                        "provides", "includes", "offers", "delivers", "enables"
                    ],
                    "moderate": [
                        "tool", "utility", "service", "option", "setting", "preference",
                        "configuration", "customization", "personalization"
                    ],
                    "weak": [
                        "thing", "item", "element", "part", "component"
                    ]
                }
            }
            
            def score_and_extract(category_patterns, sentences):
                """Score sentences based on keyword patterns and extract best matches."""
                scored_sentences = []
                
                for sentence in sentences:
                    normalized = sentence.lower()
                    score = 0
                    
                    # Score based on pattern strength
                    for strength, keywords in category_patterns.items():
                        for keyword in keywords:
                            if keyword in normalized:
                                if strength == "strong":
                                    score += 3
                                elif strength == "moderate":
                                    score += 2
                                else:  # weak
                                    score += 1
                    
                    # Bonus for requirement-specific patterns
                    if any(pattern in normalized for pattern in [
                        "shall", "must", "should", "will", "can", "enable", "allow",
                        "provide", "support", "include", "exclude", "generate", "process"
                    ]):
                        score += 1
                    
                    # Penalty for non-requirement patterns
                    if any(pattern in normalized for pattern in [
                        "introduction", "summary", "conclusion", "example", "note",
                        "figure", "table", "page", "section", "chapter"
                    ]):
                        score -= 2
                    
                    if score > 0:
                        scored_sentences.append((score, sentence))
                
                # Sort by score and return top results
                scored_sentences.sort(key=lambda x: x[0], reverse=True)
                return [sentence for score, sentence in scored_sentences[:20]]
            
            # Extract requirements for each category
            functional = score_and_extract(patterns["functional"], sentences)
            non_functional = score_and_extract(patterns["non_functional"], sentences)
            user = score_and_extract(patterns["user"], sentences)
            system = score_and_extract(patterns["system"], sentences)
            business = score_and_extract(patterns["business"], sentences)
            features = score_and_extract(patterns["features"], sentences)
            
            # Enhanced deduplication with semantic similarity
            def enhanced_dedup(items, seen_global):
                out = []
                for item in items:
                    # Normalize for deduplication
                    normalized = re.sub(r'\s+', ' ', item.strip().lower())
                    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
                    
                    if normalized in seen_global:
                        continue
                    
                    # Check for semantic similarity with existing items
                    is_similar = False
                    for existing in out:
                        existing_norm = re.sub(r'\s+', ' ', existing.strip().lower())
                        existing_norm = re.sub(r'[^a-z0-9\s]', '', existing_norm)
                        
                        # Simple similarity check based on common words
                        item_words = set(normalized.split())
                        existing_words = set(existing_norm.split())
                        
                        if len(item_words) > 0 and len(existing_words) > 0:
                            similarity = len(item_words.intersection(existing_words)) / len(item_words.union(existing_words))
                            if similarity > 0.7:  # 70% similarity threshold
                                is_similar = True
                                break
                    
                    if not is_similar:
                        seen_global.add(normalized)
                        out.append(item)
                
                return out

            # Apply enhanced deduplication
            seen_global = set()
            functional = enhanced_dedup(functional, seen_global)
            non_functional = enhanced_dedup(non_functional, seen_global)
            user = enhanced_dedup(user, seen_global)
            system = enhanced_dedup(system, seen_global)
            business = enhanced_dedup(business, seen_global)
            features = enhanced_dedup(features, seen_global)

            # STEP 2: Reclassify and deduplicate across categories
            initial_sections = {
                "functional": functional,
                "non_functional": non_functional,
                "user": user,
                "system": system,
                "business": business,
                "features": features,
            }
            
            # Reclassify all requirements to their correct categories
            reclassified = self._reclassify_and_deduplicate_all(initial_sections)
            
            # Merge system and features into functional (they're subsets)
            reclassified["functional"].extend(reclassified.get("system", []))
            reclassified["functional"].extend(reclassified.get("features", []))
            
            # Final cross-category deduplication
            final_sections = self._cross_category_deduplicate(reclassified)
            
            sections = {
                "Functional Requirements": final_sections.get("functional", []),
                "Non-Functional Requirements": final_sections.get("non_functional", []),
                "User Requirements / Stories": final_sections.get("user", []),
                "Business Requirements": final_sections.get("business", []),
            }
            
            return {"status": "success", "response": self._format_sections(sections)}
            
        except Exception as e:
            return {"status": "error", "message": f"Enhanced heuristic extraction failed: {str(e)}"}

    def _semantic_extract(self, text: str, top_k_per_class: int = 10) -> Dict[str, Any]:  # Reduced from 15 to 10 for better performance
        """Improve accuracy by ranking sentences via embedding similarity to class prompts.

        This method splits text into sentences, embeds them, and selects the most
        relevant sentences for each category based on cosine similarity to concise
        intent prompts.
        """
        try:
            import math
            import re

            content = (text or "").strip()
            if not content:
                return {"status": "success", "response": "No content."}

            # Sentence segmentation (simple, fast)
            raw_sentences = re.split(r"(?<=[.!?])\s+", content)
            sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 0]
            # Optional spaCy filter: keep imperative/actionable
            keep_mask = self._spacy_filter(sentences)
            sentences = [s for s, keep in zip(sentences, keep_mask) if keep]

            # Early exit for tiny docs
            if not sentences:
                return {"status": "success", "response": content}

            # Enhanced category prompts with more specific intent statements
            categories = {
                "functional": "Statements describing what the system shall or must do; user-visible capabilities; actions the system performs; behaviors and functionalities",
                "non_functional": "Quality attributes like performance, security, reliability, availability, usability, scalability, maintainability, portability, efficiency, robustness",
                "user": "User stories and user needs, phrased as roles, goals, benefits (As a <role>, I want <goal> so that <benefit>); user experience requirements; user interface needs",
                "system": "Technical/system requirements like APIs, databases, architecture, components, integrations, infrastructure, deployment, configuration, technical constraints",
                "business": "Business rules, constraints, policies, KPIs, compliance, ROI, regulations, standards, guidelines, business processes, stakeholder needs",
                "features": "Named features or capabilities the product provides; specific functionalities; product capabilities; feature descriptions",
            }

            # Compute embeddings
            sentence_embeddings = self.embeddings.embed_documents(sentences)
            category_names = list(categories.keys())
            category_prompts = [categories[c] for c in category_names]
            category_embeddings = self.embeddings.embed_documents(category_prompts)

            # Cosine similarity helper
            def cosine(a, b):
                dot = sum(x*y for x, y in zip(a, b))
                na = math.sqrt(sum(x*x for x in a))
                nb = math.sqrt(sum(y*y for y in b))
                if na == 0 or nb == 0:
                    return 0.0
                return dot / (na * nb)

            # Score each sentence per category
            category_to_scored = {c: [] for c in category_names}
            # Optional learning-based boost: similarity to previously learned requirements
            learned_collection = None
            try:
                learned_collection = Chroma(
                    collection_name=self.global_collection_name,
                    embedding_function=self.embeddings,
                    client=self.chroma_client
                )
            except Exception:
                learned_collection = None
            for idx, s_emb in enumerate(sentence_embeddings):
                s = sentences[idx]
                for c_idx, c_name in enumerate(category_names):
                    score = cosine(s_emb, category_embeddings[c_idx])
                    
                    # Enhanced keyword boost with category-specific patterns
                    low = s.lower()
                    
                    # Category-specific keyword boosts
                    category_keywords = {
                        "functional": ["shall", "must", "should", "will", "enable", "allow", "provide", "support", "system shall", "user can", "application shall"],
                        "non_functional": ["performance", "security", "latency", "throughput", "availability", "usability", "reliability", "scalability", "efficiency", "robustness"],
                        "user": ["as a", "as an", "user story", "persona", "role", "i want", "i need", "so that", "user experience", "user interface"],
                        "system": ["api", "database", "server", "architecture", "component", "module", "service", "endpoint", "infrastructure", "deployment"],
                        "business": ["policy", "compliance", "regulation", "standard", "guideline", "kpi", "roi", "metric", "business rule", "stakeholder"],
                        "features": ["feature", "capability", "functionality", "supports", "allows", "provides", "includes", "offers", "delivers"]
                    }
                    
                    if c_name in category_keywords:
                        keyword_matches = sum(1 for k in category_keywords[c_name] if k in low)
                        score += keyword_matches * 0.03  # Boost for each matching keyword
                    
                    # Enhanced requirement pattern detection
                    requirement_patterns = [
                        "shall", "must", "should", "will", "can", "enable", "allow", "provide", "support",
                        "include", "exclude", "generate", "process", "handle", "manage", "control", "monitor"
                    ]
                    pattern_matches = sum(1 for p in requirement_patterns if p in low)
                    score += pattern_matches * 0.02
                    
                    # Penalty for non-requirement content
                    noise_patterns = [
                        "introduction", "summary", "conclusion", "example", "note", "figure", "table",
                        "page", "section", "chapter", "appendix", "reference", "bibliography"
                    ]
                    noise_matches = sum(1 for p in noise_patterns if p in low)
                    score -= noise_matches * 0.05
                    
                    # Enhanced learned boost: if similar to any previously learned requirement
                    if learned_collection is not None:
                        try:
                            sim = learned_collection.similarity_search_with_score(s, k=1)
                            if sim and sim[0][1] is not None:
                                # Use similarity score more intelligently
                                similarity_score = sim[0][1]
                                if similarity_score > 0.7:  # High similarity threshold
                                    score += 0.1
                                elif similarity_score > 0.5:  # Medium similarity threshold
                                    score += 0.05
                        except Exception:
                            pass
                    
                    # Length-based scoring (prefer medium-length, well-formed requirements)
                    sentence_length = len(s.split())
                    if 5 <= sentence_length <= 30:  # Optimal length range
                        score += 0.02
                    elif sentence_length < 3 or sentence_length > 50:  # Too short or too long
                        score -= 0.05
                    
                    category_to_scored[c_name].append((score, s))

            # Enhanced top-k selection with improved thresholding
            results = {}
            for c in category_names:
                ranked = sorted(category_to_scored[c], key=lambda t: t[0], reverse=True)
                
                if not ranked:
                    results[c] = []
                    continue
                
                # Enhanced dynamic thresholding
                max_score = ranked[0][0]
                min_score = ranked[-1][0] if ranked else 0
                score_range = max_score - min_score
                
                # Adaptive threshold based on score distribution
                if score_range > 0.3:  # High variance - use stricter threshold
                    threshold = max_score * 0.7
                elif score_range > 0.1:  # Medium variance - moderate threshold
                    threshold = max_score * 0.5
                else:  # Low variance - use absolute threshold
                    threshold = 0.3
                
                # Enhanced filtering with multiple criteria
                keep = []
                for sc, s in ranked:
                    # Score threshold
                    if sc < threshold:
                        continue
                    
                    # Length requirements
                    if len(s) < 8 or len(s) > 200:
                        continue
                    
                    # Word count requirements
                    word_count = len(s.split())
                    if word_count < 3 or word_count > 50:
                        continue
                    
                    # Quality checks
                    if s.count('.') > 3:  # Too many sentences
                        continue
                    
                    # Enhanced requirement pattern validation
                    low = s.lower()
                    has_requirement_pattern = any(pattern in low for pattern in [
                        "shall", "must", "should", "will", "can", "enable", "allow", "provide",
                        "support", "include", "exclude", "generate", "process", "handle", "manage",
                        "control", "monitor", "track", "log", "report", "notify", "alert", "validate"
                    ])
                    
                    # Keep if it has requirement patterns or high semantic score
                    if has_requirement_pattern or sc > threshold + 0.1:
                        keep.append(s)
                    
                    # Limit to prevent too many results
                    if len(keep) >= top_k_per_class * 2:
                        break
                
                # Optional rerank against category description
                if self.use_reranker and keep:
                    keep = self._rerank(categories[c], keep, top_k=top_k_per_class)
                
                # Enhanced deduplication
                seen = set()
                dedup = []
                for s in keep:
                    # Normalize for deduplication
                    normalized = re.sub(r'\s+', ' ', s.strip().lower())
                    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
                    
                    if normalized in seen:
                        continue
                    
                    # Check for semantic similarity with existing items
                    is_similar = False
                    for existing in dedup:
                        existing_norm = re.sub(r'\s+', ' ', existing.strip().lower())
                        existing_norm = re.sub(r'[^a-z0-9\s]', '', existing_norm)
                        
                        # Word-based similarity check
                        item_words = set(normalized.split())
                        existing_words = set(existing_norm.split())
                        
                        if len(item_words) > 0 and len(existing_words) > 0:
                            similarity = len(item_words.intersection(existing_words)) / len(item_words.union(existing_words))
                            if similarity > 0.8:  # 80% similarity threshold for semantic dedup
                                is_similar = True
                                break
                    
                    if not is_similar:
                        seen.add(normalized)
                        dedup.append(s)
                
                # Remove near-duplicates by semantic similarity
                results[c] = self._near_duplicate_filter(dedup)[:top_k_per_class]

            formatted = []
            # Cross-section de-duplication to avoid repeating the same sentence in multiple sections
            def normalize_key(s: str) -> str:
                k = re.sub(r"\s+", " ", (s or "").strip()).lower()
                k = re.sub(r"[^a-z0-9 ]+", "", k)
                return k
            global_seen = set()

            def section(title, items):
                if not items:
                    return f"{title}:\n(none)"
                deduped = []
                for s in items:
                    key = normalize_key(s)
                    if key in global_seen:
                        continue
                    global_seen.add(key)
                    deduped.append(s)
                if not deduped:
                    return f"{title}:\n(none)"
                return f"{title}:\n" + "\n".join(deduped)

            # Build section dict and format consistently
            sections = {
                "Functional Requirements": results.get("functional", []),
                "Non-Functional Requirements": results.get("non_functional", []),
                "User Requirements / Stories": results.get("user", []),
                "System Requirements": results.get("system", []),
                "Business Requirements": results.get("business", []),
                "Features": results.get("features", []),
            }

            # Also learn from the current extraction (best-effort)
            try:
                self._learn_from_results(filename=self.last_source or "unknown", sections=sections)
                # Force save after learning from results for user-specific agents
                if self.user_id is not None and self.enable_self_learning:
                    self._save_learned_patterns()
            except Exception:
                pass

            response_text = self._format_sections(sections)
            # Optional LLM finalize
            response_text = self._llm_finalize(response_text)
            return {"status": "success", "response": response_text}
        except Exception as e:
            return {"status": "error", "message": f"Semantic extraction failed: {str(e)}"}

    def _advanced_pattern_extract(self, text: str) -> Dict[str, Any]:
        """Advanced pattern-based extraction using regex and NLP techniques."""
        try:
            content = (text or "").strip()
            if not content:
                return {"status": "success", "response": "No content to analyze."}
            
            # Advanced regex patterns for different requirement types
            patterns = {
                "functional": [
                    r"(?:system|application|software|platform|user)\s+(?:shall|must|should|will|can)\s+[^.!?]*(?:[.!?]|$)",
                    r"(?:shall|must|should|will|can)\s+(?:enable|allow|provide|support|include|exclude|generate|process|handle|manage|control|monitor|track|log|report|notify|alert|validate)[^.!?]*(?:[.!?]|$)",
                    r"(?:enable|allow|provide|support|include|exclude|generate|process|handle|manage|control|monitor|track|log|report|notify|alert|validate)[^.!?]*(?:[.!?]|$)",
                ],
                "non_functional": [
                    r"(?:performance|latency|throughput|availability|security|encryption|usability|reliability|scalability|maintainability|portability|compatibility|accessibility|efficiency|robustness)[^.!?]*(?:[.!?]|$)",
                    r"(?:response time|uptime|downtime|bandwidth|memory usage|cpu usage|storage capacity|load capacity|concurrent users)[^.!?]*(?:[.!?]|$)",
                    r"(?:quality|standard|requirement|constraint|limit|threshold|metric|measurement|benchmark|criteria)[^.!?]*(?:[.!?]|$)",
                ],
                "user": [
                    r"(?:as a|as an|as the)[^.!?]*(?:[.!?]|$)",
                    r"(?:i want|i need|i should|i can)[^.!?]*(?:[.!?]|$)",
                    r"(?:so that|in order to)[^.!?]*(?:[.!?]|$)",
                    r"(?:user story|persona|role|actor|stakeholder)[^.!?]*(?:[.!?]|$)",
                ],
                "system": [
                    r"(?:architecture|server|database|api|endpoint|service|component|module|framework|library|infrastructure|deployment|configuration|integration)[^.!?]*(?:[.!?]|$)",
                    r"(?:technical|system|application|software|platform|environment|technology|implementation|development)[^.!?]*(?:[.!?]|$)",
                ],
                "business": [
                    r"(?:business rule|policy|compliance|regulation|standard|guideline|kpi|roi|metric|measurement|threshold|limit|constraint|restriction|rule|procedure)[^.!?]*(?:[.!?]|$)",
                    r"(?:business|stakeholder|requirement|objective|goal|strategy|process|workflow|approval|authorization)[^.!?]*(?:[.!?]|$)",
                ],
                "features": [
                    r"(?:feature|capability|functionality|supports|allows|provides|includes|offers|delivers|enables)[^.!?]*(?:[.!?]|$)",
                    r"(?:tool|utility|service|option|setting|preference|configuration|customization|personalization)[^.!?]*(?:[.!?]|$)",
                ]
            }
            
            def extract_with_patterns(category_patterns, text):
                """Extract sentences matching patterns for a category."""
                matches = []
                for pattern in category_patterns:
                    found = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                    matches.extend(found)
                
                # Clean and normalize matches
                cleaned = []
                for match in matches:
                    cleaned_match = self._normalize_line(match.strip())
                    if cleaned_match and self._should_keep_line(cleaned_match):
                        cleaned.append(cleaned_match)
                
                # Remove duplicates while preserving order
                seen = set()
                unique = []
                for item in cleaned:
                    normalized = re.sub(r'\s+', ' ', item.lower().strip())
                    if normalized not in seen:
                        seen.add(normalized)
                        unique.append(item)
                
                return unique[:15]  # Limit to top 15 per category
            
            # Extract requirements for each category
            functional = extract_with_patterns(patterns["functional"], content)
            non_functional = extract_with_patterns(patterns["non_functional"], content)
            user = extract_with_patterns(patterns["user"], content)
            system = extract_with_patterns(patterns["system"], content)
            business = extract_with_patterns(patterns["business"], content)
            features = extract_with_patterns(patterns["features"], content)
            
            sections = {
                "Functional Requirements": functional,
                "Non-Functional Requirements": non_functional,
                "User Requirements / Stories": user,
                "System Requirements": system,
                "Business Requirements": business,
                "Features": features,
            }
            
            return {"status": "success", "response": self._format_sections(sections)}
            
        except Exception as e:
            return {"status": "error", "message": f"Advanced pattern extraction failed: {str(e)}"}

    def extract_requirements(self, query: str = None) -> Dict[str, Any]:
        """Enhanced requirement extraction with self-learning capabilities."""
        try:
            if query is None:
                query = "Extract all features, requirements, and specifications from the documents. Organize them by type (functional, non-functional, user, system, business) and provide specific examples."

            # Get document text
            if self.vectorstore is not None:
                where = {"source": self.last_source} if getattr(self, "last_source", None) else None
                try:
                    # Optimize: Use reasonable k value (50 instead of 100) for better performance
                    # Can be increased if needed, but 50 chunks is usually sufficient
                    docs = self.vectorstore.similarity_search("", k=50, filter=where)
                except TypeError:
                    # older langchain may use `where` instead of `filter`
                    docs = self.vectorstore.similarity_search("", k=50, where=where)  # type: ignore
                text = "\n".join([d.page_content for d in docs])
            else:
                text = ""
            
            # Apply learned patterns first (if available) - enhanced integration
            learned_results = {}
            if self.enable_self_learning and text:
                learned_results = self._apply_learned_patterns(text)
                if learned_results:
                    print(f"🧠 Applied learned patterns: found {sum(len(v) for v in learned_results.values())} additional requirements")
            
            # Try multiple extraction methods - optimized order: fastest first
            # Heuristic is fastest (pattern matching), then pattern (learned), then semantic (embeddings - slowest)
            methods = [
                ("heuristic", self._heuristic_extract),  # Fastest - pattern matching
                ("pattern", self._advanced_pattern_extract),  # Medium - learned patterns
                ("semantic", self._semantic_extract)  # Slowest - embedding-based, try last
            ]
            
            best_result = None
            best_score = 0
            method_used = "none"
            last_error = None
            
            for method_name, method_func in methods:
                try:
                    print(f"🔄 Trying {method_name} extraction method...")
                    result = method_func(text)
                    
                    # Debug: Show what we got
                    print(f"  📊 {method_name} result status: {result.get('status')}")
                    print(f"  📊 {method_name} has response: {bool(result.get('response'))}")
                    if result.get("response"):
                        print(f"  📊 {method_name} response length: {len(str(result.get('response')))}")
                    
                    if result.get("status") == "success" and result.get("response"):
                        # Check if we got meaningful results
                        response = result.get("response", "")
                        if len(response.strip()) > 50:  # Ensure we have substantial content
                            # Calculate quality score
                            quality_score = len(response.strip())
                            
                            # Merge with learned results if available
                            if learned_results:
                                # Add learned patterns info to response
                                learned_info = f"\n\nLearned patterns applied: {sum(len(reqs) for reqs in learned_results.values())} additional requirements found."
                                response += learned_info
                                quality_score += len(learned_info)
                            
                            if quality_score > best_score:
                                best_score = quality_score
                                best_result = result
                                method_used = method_name
                        else:
                            print(f"  ⚠️ {method_name} response too short: {len(response.strip())} chars")
                    else:
                        if result.get("message"):
                            print(f"  ❌ {method_name} error: {result.get('message')}")
                                
                except Exception as e:
                    last_error = e
                    print(f"⚠️ {method_name} extraction exception: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Use learned patterns if no other method worked
            if not best_result and learned_results:
                learned_text = self._format_learned_results(learned_results)
                if len(learned_text.strip()) > 50:
                    best_result = {
                        "status": "success",
                        "response": learned_text,
                        "method": "learned_patterns"
                    }
                    method_used = "learned_patterns"
            
            if best_result:
                # Ensure best_result has required fields
                if not best_result.get("response"):
                    best_result["response"] = "No requirements extracted."
                if not best_result.get("status"):
                    best_result["status"] = "success"
                
                # Learn from successful extraction - merge learned results with extraction results
                if self.enable_self_learning and text:
                    # Parse the best result to extract sections for learning
                    response_text = best_result.get("response", "")
                    # Extract sections from formatted response
                    sections_to_learn = self._parse_response_to_sections(response_text)
                    # Merge with learned results
                    merged_sections = {}
                    for category, items in sections_to_learn.items():
                        merged_sections[category] = list(set(items + learned_results.get(category, [])))
                    
                    # Learn from merged sections
                    if merged_sections:
                        total_before = sum(len(patterns['keywords']) + len(patterns['phrases']) + len(patterns['patterns']) for patterns in self.learned_patterns.values())
                        self._learn_from_extraction(text, merged_sections, getattr(self, "last_source", ""))
                        total_after = sum(len(patterns['keywords']) + len(patterns['phrases']) + len(patterns['patterns']) for patterns in self.learned_patterns.values())
                        improvement = total_after - total_before
                        if improvement > 0:
                            print(f"📈 Knowledge base improved: +{improvement} new patterns (total: {total_after})")
                
                # Update performance metrics with enhanced tracking
                success = best_result.get("status") == "success"
                categories_found = list(learned_results.keys()) if learned_results else []
                # Also extract categories from best result
                response_text = best_result.get("response", "")
                parsed_categories = self._parse_response_to_sections(response_text)
                categories_found.extend(list(parsed_categories.keys()))
                categories_found = list(set(categories_found))  # Remove duplicates
                self._update_performance_metrics(method_used, success, categories_found)
                
                # Add learning info to result
                best_result["extraction_method"] = method_used
                best_result["learning_enabled"] = self.enable_self_learning
                best_result["quality_score"] = best_score
                
                print(f"✅ Used {method_used} extraction method")
                print(f"📊 Result status: {best_result.get('status')}, Response length: {len(str(best_result.get('response', '')))}")
                return best_result
            
            # If all methods failed, return error
            return {
                "status": "error",
                "message": f"All extraction methods failed. Last error: {str(last_error)}"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error extracting requirements: {str(e)}"
            }
    
    def get_document_summary(self) -> Dict[str, Any]:
        """Get a summary of all processed documents."""
        try:
            response = self.agent.invoke({"input": "Provide a comprehensive summary of all processed documents, focusing on the main features, requirements, and specifications."})
            
            return {
                "status": "success",
                "summary": response["output"]
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error creating summary: {str(e)}"
            }
    
    def search_specific_requirements(self, requirement_type: str) -> Dict[str, Any]:
        """Search for specific types of requirements."""
        try:
            query = f"Extract all {requirement_type} requirements from the documents. Provide specific examples and details."
            response = self.agent.invoke({"input": query})
            
            return {
                "status": "success",
                "requirement_type": requirement_type,
                "requirements": response["output"]
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error searching {requirement_type} requirements: {str(e)}"
            }

# Global agent instance cache
agent_instance = None
user_agent_cache = {}  # Cache for user-specific agents

def get_agent(user_id: Optional[int] = None) -> RequirementsExtractionAgent:
    """Get or create agent instance, optionally user-specific.
    Uses caching to avoid re-initialization on subsequent calls.
    
    Args:
        user_id: Optional user ID for user-specific learning. If provided,
                 creates a user-specific agent instance (cached per user_id).
    
    Returns:
        RequirementsExtractionAgent instance
    """
    global agent_instance, user_agent_cache
    
    # If user_id provided, use user-specific cache
    if user_id is not None:
        if user_id not in user_agent_cache:
            print(f"🔄 Creating new agent instance for user_id={user_id} (first time)")
            user_agent_cache[user_id] = RequirementsExtractionAgent("", user_id=user_id)
            print(f"✅ Agent cached for user_id={user_id}")
        else:
            print(f"✅ Using cached agent for user_id={user_id}")
        return user_agent_cache[user_id]
    
    # Otherwise use global instance
    if agent_instance is None:
        print("🔄 Creating global agent instance (first time)")
        agent_instance = RequirementsExtractionAgent("")
        print("✅ Global agent cached")
    else:
        print("✅ Using cached global agent")
    return agent_instance
