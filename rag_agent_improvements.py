# FlowMind Requirements Extraction - Enhanced Classification & Deduplication
# This file contains improved logic that will be integrated into rag_agent.py

import re
from typing import List, Dict, Set, Tuple

def is_valid_requirement(sentence: str) -> bool:
    """Filter out non-requirements like dates, project info, metadata."""
    normalized = sentence.lower().strip()
    
    # Minimum length check
    if len(normalized) < 15:
        return False
    
    # Exclude pure metadata, headers, dates
    exclude_patterns = [
        r'^\d+\.?\s*$',  # Just numbers
        r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',  # Starts with month
        r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # Dates
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
        r'timeline.*(jan|feb|mar|apr|may|june|july|aug|sep|oct|nov|dec|\d{4})',
        r'expected.*\d{4}',  # Expected dates
        r'delivery.*\d{4}',  # Delivery dates
        r'due.*\d{4}',  # Due dates
        r'^(page|section|chapter|figure|table|appendix)\s+\d+',  # Document structure
        r'^(version|revision|date|author|title)',  # Document metadata
        r'^(introduction|summary|conclusion|abstract|overview|background)',  # Document sections
        r'^\s*(#|##|###)',  # Markdown headers
    ]
    
    for pattern in exclude_patterns:
        if re.search(pattern, normalized):
            return False
    
    # Exclude pure questions or incomplete thoughts
    if normalized.endswith('?') and len(normalized.split()) < 8:
        return False
    
    # Require some requirement-like indicators
    requirement_indicators = [
        'must', 'shall', 'should', 'will', 'can', 'may',
        'enable', 'allow', 'provide', 'support', 'include',
        'process', 'handle', 'manage', 'generate', 'validate',
        'bot', 'system', 'application', 'platform', 'user',
        'performance', 'security', 'reliability', 'scalability',
        'as a', 'i want', 'i need'
    ]
    
    has_indicator = any(indicator in normalized for indicator in requirement_indicators)
    if not has_indicator:
        return False
    
    return True


def classify_requirement(sentence: str) -> str:
    """
    Improved classification that correctly distinguishes between requirement types.
    Returns: 'functional', 'non_functional', 'user', or 'business'
    """
    normalized = sentence.lower().strip()
    
    # PRIORITY 1: User Stories (highest priority, most specific)
    user_story_patterns = [
        r'as\s+(a|an|the)\s+\w+',  # "as a user"
        r'i\s+(want|need|should|can|will)',  # "I want to"
        r'so\s+that',  # "so that I can"
        r'user\s+story',
        r'user\s+(experience|interface|journey|workflow|interaction)',
    ]
    
    if any(re.search(pattern, normalized) for pattern in user_story_patterns):
        return 'user'
    
    # PRIORITY 2: Non-Functional (quality attributes, NOT business processes)
    # These describe HOW well the system performs, not WHAT it does
    nfr_indicators = {
        # Performance
        'performance', 'latency', 'throughput', 'response time', 'speed',
        'load time', 'processing time', 'execution time',
        # Security
        'security', 'encryption', 'authentication', 'authorization',
        'secure', 'encrypted', 'protected', 'verified',
        # Reliability & Availability
        'reliability', 'availability', 'uptime', 'downtime', 'failover',
        'fault tolerant', 'disaster recovery', 'backup',
        # Scalability
        'scalability', 'scalable', 'scale', 'concurrent users', 'load capacity',
        'horizontal scaling', 'vertical scaling',
        # Usability
        'usability', 'user-friendly', 'intuitive', 'ease of use',
        'accessible', 'accessibility',
        # Maintainability
        'maintainability', 'maintainable', 'modular', 'extensible',
        'testable', 'debuggable',
        # Portability & Compatibility
        'portability', 'portable', 'compatibility', 'compatible',
        'cross-platform', 'browser compatibility',
        # Efficiency
        'efficiency', 'efficient', 'optimized', 'memory usage',
        'cpu usage', 'bandwidth', 'storage capacity',
        # Standards & Compliance (non-functional aspect)
        'standard compliance', 'iso', 'gdpr', 'hipaa', 'pci',
    }
    
    # Check if sentence is about quality attributes
    nfr_count = sum(1 for indicator in nfr_indicators if indicator in normalized)
    
    # Strong NFR signals
    nfr_strong_patterns = [
        r'(must|shall|should)\s+(be|have|provide|support|maintain|ensure)\s+(performant|secure|reliable|available|scalable|usable)',
        r'response\s+time\s+(must|shall|should|will)',
        r'within\s+\d+\s*(ms|millisecond|second|minute)',
        r'\d+%\s+(uptime|availability)',
        r'concurrent\s+users',
        r'requests\s+per\s+second',
    ]
    
    has_nfr_strong = any(re.search(pattern, normalized) for pattern in nfr_strong_patterns)
    
    # NFR should NOT be confused with functional payment/business processes
    functional_business_keywords = [
        'collect', 'charge', 'payment', 'deposit', 'invoice', 'bill',
        'calculate', 'compute', 'fetch', 'gather', 'book', 'reserve',
        'assign', 'schedule', 'process order', 'handle request'
    ]
    
    has_functional_business = any(keyword in normalized for keyword in functional_business_keywords)
    
    # If it has strong NFR signals and NO functional business keywords
    if (has_nfr_strong or nfr_count >= 2) and not has_functional_business:
        return 'non_functional'
    
    # PRIORITY 3: Business Rules & Policies
    business_indicators = {
        'business rule', 'policy', 'regulation', 'compliance',
        'guideline', 'standard', 'approval', 'authorization',
        'workflow', 'procedure', 'stakeholder', 'kpi', 'roi',
        'metric', 'threshold', 'limit', 'constraint',
    }
    
    business_count = sum(1 for indicator in business_indicators if indicator in normalized)
    
    # Patterns specific to business constraints (not technical)
    business_patterns = [
        r'business\s+(rule|policy|requirement|constraint)',
        r'(approved|approval)\s+by',
        r'stakeholder',
        r'(kpi|roi|metric)',
    ]
    
    if business_count >= 1 or any(re.search(pattern, normalized) for pattern in business_patterns):
        return 'business'
    
    # PRIORITY 4: Functional (default for most action-oriented requirements)
    # These describe WHAT the system does
    functional_indicators = {
        # Strong action verbs
        'must', 'shall', 'should', 'will',
        # System actions
        'collect', 'fetch', 'gather', 'calculate', 'compute', 'generate',
        'process', 'handle', 'manage', 'store', 'retrieve', 'display',
        'send', 'receive', 'validate', 'verify', 'check', 'confirm',
        'create', 'update', 'delete', 'modify', 'add', 'remove',
        'book', 'reserve', 'assign', 'schedule', 'allocate',
        'charge', 'pay', 'invoice', 'bill', 'deposit',
        # Bot/system capabilities
        'bot must', 'system must', 'application must', 'platform must',
        'bot shall', 'system shall', 'application shall',
        # Enabling/allowing
        'enable', 'allow', 'provide', 'support', 'include',
        'differentiate', 'distinguish', 'categorize',
    }
    
    functional_count = sum(1 for indicator in functional_indicators if indicator in normalized)
    
    # Strong functional patterns
    functional_patterns = [
        r'(bot|system|application|platform)\s+(must|shall|should|will|can)',
        r'(must|shall|should|will)\s+(collect|fetch|gather|calculate|compute|generate|process)',
        r'(must|shall|should|will)\s+(book|reserve|assign|schedule)',
        r'(must|shall|should|will)\s+(charge|pay|invoice)',
        r'(must|shall|should|will)\s+(not|avoid|prevent|skip)',
        r'using\s+(api|google\s+maps|rate\s+sheet)',
    ]
    
    has_functional_strong = any(re.search(pattern, normalized) for pattern in functional_patterns)
    
    if functional_count >= 2 or has_functional_strong:
        return 'functional'
    
    # Default: Functional (most requirements are functional)
    return 'functional'


def advanced_deduplicate_across_categories(
    categorized_reqs: Dict[str, List[str]],
    similarity_threshold: float = 0.75
) -> Dict[str, List[str]]:
    """
    Advanced deduplication that removes duplicates across ALL categories.
    Keeps the requirement in the category where it scores highest.
    """
    
    # Step 1: Collect all requirements with their categories
    all_reqs: List[Tuple[str, str, str]] = []  # (original_text, normalized, category)
    
    for category, reqs in categorized_reqs.items():
        for req in reqs:
            normalized = re.sub(r'\s+', ' ', req.strip().lower())
            normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
            all_reqs.append((req, normalized, category))
    
    # Step 2: Find duplicates using multiple strategies
    seen_normalized: Set[str] = set()
    seen_keys: Set[str] = set()
    kept_reqs: List[Tuple[str, str, str]] = []
    
    for original, normalized, category in all_reqs:
        # Strategy 1: Exact normalized match
        if normalized in seen_normalized:
            continue
        
        # Strategy 2: Core text extraction (remove common prefixes)
        core_text = normalized
        # Remove common prefixes like "bot must", "system must", etc.
        for prefix in ['bot must', 'system must', 'application must', 'platform must',
                       'bot shall', 'system shall', 'must', 'shall', 'should', 'will']:
            if core_text.startswith(prefix):
                core_text = core_text[len(prefix):].strip()
                break
        
        # Create a key from core content words (ignore common words)
        words = core_text.split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
                      'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did'}
        content_words = [w for w in words if w not in stop_words and len(w) > 2]
        core_key = ' '.join(sorted(content_words[:8]))  # Use first 8 content words, sorted
        
        if core_key in seen_keys and len(core_key) > 10:
            continue
        
        # Strategy 3: Jaccard similarity check against existing kept requirements
        is_duplicate = False
        current_words = set(normalized.split())
        
        for _, kept_normalized, _ in kept_reqs:
            kept_words = set(kept_normalized.split())
            
            # Jaccard similarity
            if len(current_words) > 0 and len(kept_words) > 0:
                intersection = len(current_words.intersection(kept_words))
                union = len(current_words.union(kept_words))
                similarity = intersection / union if union > 0 else 0
                
                # Also check substring containment (one is subset of other)
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break
                
                # Check if one is largely contained in the other
                if len(current_words) > 4 and len(kept_words) > 4:
                    containment_forward = intersection / len(current_words)
                    containment_backward = intersection / len(kept_words)
                    if containment_forward >= 0.85 or containment_backward >= 0.85:
                        is_duplicate = True
                        break
        
        if is_duplicate:
            continue
        
        # Keep this requirement
        seen_normalized.add(normalized)
        if core_key and len(core_key) > 10:
            seen_keys.add(core_key)
        kept_reqs.append((original, normalized, category))
    
    # Step 3: Rebuild categorized dict
    result: Dict[str, List[str]] = {cat: [] for cat in categorized_reqs.keys()}
    
    for original, _, category in kept_reqs:
        result[category].append(original)
    
    return result


def enhanced_requirement_scoring(sentence: str, category: str) -> float:
    """
    Score how well a sentence fits a particular category.
    Higher score = better fit.
    """
    normalized = sentence.lower().strip()
    score = 0.0
    
    # Category-specific scoring
    if category == 'functional':
        functional_keywords = [
            'must', 'shall', 'should', 'will',
            'collect', 'fetch', 'gather', 'calculate', 'compute',
            'process', 'handle', 'book', 'reserve', 'assign',
            'charge', 'payment', 'deposit', 'invoice'
        ]
        score += sum(3 if kw in normalized else 0 for kw in functional_keywords)
        
        if re.search(r'(bot|system|application)\s+(must|shall|should)', normalized):
            score += 5
        if 'using' in normalized and ('api' in normalized or 'maps' in normalized):
            score += 3
            
    elif category == 'non_functional':
        nfr_keywords = [
            'performance', 'security', 'reliability', 'availability',
            'scalability', 'usability', 'latency', 'throughput',
            'response time', 'uptime', 'concurrent users'
        ]
        score += sum(4 if kw in normalized else 0 for kw in nfr_keywords)
        
        if re.search(r'\d+\s*(ms|second|minute|%)', normalized):
            score += 4
        if 'within' in normalized and re.search(r'\d+', normalized):
            score += 3
            
    elif category == 'user':
        if re.search(r'as\s+(a|an)\s+\w+', normalized):
            score += 10
        if 'i want' in normalized or 'i need' in normalized:
            score += 8
        if 'so that' in normalized:
            score += 5
        if 'user experience' in normalized or 'user interface' in normalized:
            score += 4
            
    elif category == 'business':
        business_keywords = [
            'business rule', 'policy', 'compliance', 'regulation',
            'approval', 'stakeholder', 'kpi', 'roi'
        ]
        score += sum(4 if kw in normalized else 0 for kw in business_keywords)
    
    return score


def consolidate_and_reclassify(
    initial_categories: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """
    Main function: Reclassify requirements to correct category and deduplicate.
    """
    # Step 1: Validate and filter requirements
    valid_reqs: Dict[str, List[str]] = {cat: [] for cat in initial_categories.keys()}
    
    for category, reqs in initial_categories.items():
        for req in reqs:
            if is_valid_requirement(req):
                valid_reqs[category].append(req)
    
    # Step 2: Reclassify each requirement to its best category
    all_reqs_with_scores: List[Tuple[str, str, float]] = []  # (req, category, score)
    
    for category, reqs in valid_reqs.items():
        for req in reqs:
            # Get the best category for this requirement
            best_category = classify_requirement(req)
            score = enhanced_requirement_scoring(req, best_category)
            all_reqs_with_scores.append((req, best_category, score))
    
    # Step 3: Build reclassified dict
    reclassified: Dict[str, List[str]] = {
        'functional': [],
        'non_functional': [],
        'user': [],
        'business': []
    }
    
    for req, category, score in all_reqs_with_scores:
        reclassified[category].append(req)
    
    # Step 4: Advanced cross-category deduplication
    final_result = advanced_deduplicate_across_categories(reclassified, similarity_threshold=0.75)
    
    # Map back to original category names
    result = {
        "Functional Requirements": final_result.get('functional', []),
        "Non-Functional Requirements": final_result.get('non_functional', []),
        "User Requirements / Stories": final_result.get('user', []),
        "Business Requirements": final_result.get('business', []),
    }
    
    return result

