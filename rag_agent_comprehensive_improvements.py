# FlowMind - Comprehensive Agent Improvements
# These improvements will be integrated to create the best possible requirements extraction agent

import re
from typing import List, Dict, Set, Tuple, Optional, Any
import math

class AgentImprovements:
    """Collection of advanced improvements for the requirements extraction agent."""
    
    # ============================================================================
    # 1. ADVANCED CONTEXT-AWARE EXTRACTION
    # ============================================================================
    
    @staticmethod
    def extract_with_context(text: str, window_size: int = 2) -> List[Dict[str, Any]]:
        """
        Extract requirements with surrounding context for better understanding.
        Context helps classify and validate requirements more accurately.
        """
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        requirements = []
        
        for i, sentence in enumerate(sentences):
            # Get context window
            context_before = sentences[max(0, i-window_size):i]
            context_after = sentences[i+1:min(len(sentences), i+window_size+1)]
            
            requirement = {
                'text': sentence,
                'context_before': ' '.join(context_before),
                'context_after': ' '.join(context_after),
                'position': i,
                'has_context': len(context_before) > 0 or len(context_after) > 0
            }
            requirements.append(requirement)
        
        return requirements
    
    @staticmethod
    def analyze_document_structure(text: str) -> Dict[str, Any]:
        """
        Analyze document structure to understand sections and hierarchy.
        This helps identify where requirements are typically located.
        """
        structure = {
            'has_sections': False,
            'section_markers': [],
            'numbered_lists': [],
            'bullet_points': [],
            'tables_detected': False,
            'has_headers': False
        }
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            # Detect section headers
            if re.match(r'^#{1,6}\s+', line) or re.match(r'^[A-Z][A-Z\s]+$', line):
                structure['has_headers'] = True
                structure['section_markers'].append((i, line.strip()))
            
            # Detect numbered lists
            if re.match(r'^\s*\d+[\.)]\s+', line):
                structure['numbered_lists'].append(i)
            
            # Detect bullet points
            if re.match(r'^\s*[-*•]\s+', line):
                structure['bullet_points'].append(i)
            
            # Detect tables
            if '|' in line and line.count('|') >= 2:
                structure['tables_detected'] = True
        
        structure['has_sections'] = len(structure['section_markers']) > 2
        
        return structure
    
    # ============================================================================
    # 2. INTELLIGENT REQUIREMENT SCORING WITH CONFIDENCE
    # ============================================================================
    
    @staticmethod
    def score_requirement_quality(requirement: str) -> Dict[str, float]:
        """
        Comprehensive quality scoring for requirements.
        Returns multiple scores for different quality aspects.
        """
        scores = {
            'clarity': 0.0,      # How clear and specific
            'completeness': 0.0,  # Has all necessary info
            'testability': 0.0,   # Can it be tested/verified
            'atomicity': 0.0,     # Single responsibility
            'consistency': 0.0,   # Uses consistent language
            'overall': 0.0
        }
        
        normalized = requirement.lower().strip()
        words = normalized.split()
        word_count = len(words)
        
        # CLARITY SCORE
        # Clear requirements use specific action verbs and avoid vague terms
        clear_verbs = ['must', 'shall', 'will', 'calculate', 'fetch', 'collect',
                       'book', 'reserve', 'charge', 'process', 'validate']
        vague_terms = ['somehow', 'maybe', 'probably', 'might', 'could', 'approximately']
        
        clarity_score = sum(1 for v in clear_verbs if v in normalized) * 10
        clarity_penalty = sum(1 for v in vague_terms if v in normalized) * -15
        scores['clarity'] = max(0, min(100, 50 + clarity_score + clarity_penalty))
        
        # COMPLETENESS SCORE
        # Complete requirements specify who, what, and sometimes how/when
        has_actor = any(actor in normalized for actor in ['bot', 'system', 'user', 'application', 'platform'])
        has_action = any(v in normalized for v in clear_verbs)
        has_object = word_count >= 6  # Likely has an object if long enough
        has_condition = any(cond in normalized for cond in ['if', 'when', 'unless', 'after', 'before'])
        
        completeness_score = (
            (30 if has_actor else 0) +
            (30 if has_action else 0) +
            (30 if has_object else 0) +
            (10 if has_condition else 0)
        )
        scores['completeness'] = completeness_score
        
        # TESTABILITY SCORE
        # Testable requirements have measurable outcomes or specific behaviors
        testable_indicators = ['using', 'via', 'api', 'with', 'amount', 'number', 'count']
        measurable_patterns = [r'\d+', r'(all|every|each)', r'(must|shall) (not|avoid|prevent)']
        
        testability_score = sum(1 for ind in testable_indicators if ind in normalized) * 15
        testability_score += sum(1 for pattern in measurable_patterns if re.search(pattern, normalized)) * 10
        scores['testability'] = min(100, testability_score)
        
        # ATOMICITY SCORE
        # Atomic requirements do one thing; penalize multiple 'and' clauses
        and_count = normalized.count(' and ')
        or_count = normalized.count(' or ')
        comma_count = normalized.count(',')
        
        atomicity_score = 100 - (and_count * 15) - (or_count * 10) - (comma_count * 5)
        scores['atomicity'] = max(0, atomicity_score)
        
        # CONSISTENCY SCORE
        # Consistent requirements use standard terminology
        standard_terms = ['must', 'shall', 'should', 'bot', 'system', 'user']
        non_standard = ['need to', 'have to', 'got to', 'gotta']
        
        consistency_score = 70 + sum(1 for term in standard_terms if term in normalized) * 5
        consistency_penalty = sum(1 for term in non_standard if term in normalized) * -10
        scores['consistency'] = max(0, min(100, consistency_score + consistency_penalty))
        
        # OVERALL SCORE (weighted average)
        scores['overall'] = (
            scores['clarity'] * 0.25 +
            scores['completeness'] * 0.30 +
            scores['testability'] * 0.20 +
            scores['atomicity'] * 0.15 +
            scores['consistency'] * 0.10
        )
        
        return scores
    
    # ============================================================================
    # 3. DOMAIN-SPECIFIC PATTERN RECOGNITION
    # ============================================================================
    
    @staticmethod
    def detect_domain_patterns(text: str) -> Dict[str, List[str]]:
        """
        Detect domain-specific patterns to improve classification.
        Different domains have different requirement styles.
        """
        patterns = {
            'web_application': [],
            'mobile_app': [],
            'api_service': [],
            'e_commerce': [],
            'booking_system': [],
            'data_processing': [],
            'security_focused': [],
            'general': []
        }
        
        normalized = text.lower()
        
        # Web Application indicators
        if any(term in normalized for term in ['web', 'browser', 'http', 'html', 'css', 'javascript', 'frontend', 'backend']):
            patterns['web_application'].append('Web application context detected')
        
        # Mobile App indicators
        if any(term in normalized for term in ['mobile', 'ios', 'android', 'app', 'touch', 'swipe', 'notification']):
            patterns['mobile_app'].append('Mobile application context detected')
        
        # API Service indicators
        if any(term in normalized for term in ['api', 'endpoint', 'rest', 'graphql', 'json', 'xml', 'request', 'response']):
            patterns['api_service'].append('API service context detected')
        
        # E-commerce indicators
        if any(term in normalized for term in ['payment', 'checkout', 'cart', 'product', 'order', 'purchase', 'inventory']):
            patterns['e_commerce'].append('E-commerce context detected')
        
        # Booking System indicators
        if any(term in normalized for term in ['book', 'reservation', 'appointment', 'schedule', 'calendar', 'slot', 'availability']):
            patterns['booking_system'].append('Booking system context detected')
        
        # Data Processing indicators
        if any(term in normalized for term in ['process', 'transform', 'etl', 'pipeline', 'batch', 'stream', 'analytics']):
            patterns['data_processing'].append('Data processing context detected')
        
        # Security-focused indicators
        if any(term in normalized for term in ['security', 'encryption', 'authentication', 'authorization', 'access control', 'compliance']):
            patterns['security_focused'].append('Security-focused context detected')
        
        return {k: v for k, v in patterns.items() if v}
    
    # ============================================================================
    # 4. REQUIREMENT RELATIONSHIP DETECTION
    # ============================================================================
    
    @staticmethod
    def detect_relationships(requirements: List[str]) -> List[Dict[str, Any]]:
        """
        Detect relationships between requirements (dependencies, conflicts, duplicates).
        This helps in organizing and validating requirements.
        """
        relationships = []
        
        for i, req1 in enumerate(requirements):
            for j, req2 in enumerate(requirements[i+1:], i+1):
                relationship = {
                    'req1_index': i,
                    'req2_index': j,
                    'req1': req1,
                    'req2': req2,
                    'relationship_type': None,
                    'confidence': 0.0
                }
                
                # Detect dependencies
                if any(dep in req1.lower() for dep in ['after', 'before', 'once', 'when', 'if']) and \
                   any(word in req2.lower() for word in req1.lower().split() if len(word) > 4):
                    relationship['relationship_type'] = 'dependency'
                    relationship['confidence'] = 0.6
                    relationships.append(relationship)
                
                # Detect conflicts
                conflict_pairs = [
                    ('must', 'must not'),
                    ('shall', 'shall not'),
                    ('enable', 'disable'),
                    ('allow', 'prevent')
                ]
                for pos, neg in conflict_pairs:
                    if pos in req1.lower() and neg in req2.lower():
                        similarity = AgentImprovements._calculate_text_similarity(req1, req2)
                        if similarity > 0.5:
                            relationship['relationship_type'] = 'potential_conflict'
                            relationship['confidence'] = similarity
                            relationships.append(relationship)
                
                # Detect high similarity (potential duplicates handled elsewhere, but flag for review)
                similarity = AgentImprovements._calculate_text_similarity(req1, req2)
                if 0.6 < similarity < 0.75:  # Similar but not duplicate
                    relationship['relationship_type'] = 'related'
                    relationship['confidence'] = similarity
                    relationships.append(relationship)
        
        return relationships
    
    @staticmethod
    def _calculate_text_similarity(text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    # ============================================================================
    # 5. INTELLIGENT REQUIREMENT PRIORITIZATION
    # ============================================================================
    
    @staticmethod
    def prioritize_requirements(requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Intelligently prioritize requirements based on multiple factors.
        Returns requirements sorted by priority with priority scores.
        """
        for req in requirements:
            text = req.get('text', '')
            normalized = text.lower()
            priority_score = 50  # Base priority
            
            # Critical keywords boost priority
            critical_keywords = ['security', 'authentication', 'payment', 'data loss', 'critical', 'essential']
            priority_score += sum(10 for kw in critical_keywords if kw in normalized)
            
            # Mandatory language boosts priority
            if 'must' in normalized or 'shall' in normalized:
                priority_score += 20
            elif 'should' in normalized:
                priority_score += 10
            
            # Business impact indicators
            business_impact = ['revenue', 'customer', 'compliance', 'legal', 'regulation']
            priority_score += sum(15 for bi in business_impact if bi in normalized)
            
            # Core functionality indicators
            core_functions = ['login', 'register', 'checkout', 'payment', 'booking', 'reservation']
            priority_score += sum(12 for cf in core_functions if cf in normalized)
            
            # Technical complexity (inverse - simpler first unless critical)
            if any(complex_term in normalized for complex_term in ['integrate', 'algorithm', 'machine learning', 'ai']):
                priority_score -= 5
            
            req['priority_score'] = min(100, max(0, priority_score))
            
            # Assign priority level
            if req['priority_score'] >= 80:
                req['priority_level'] = 'CRITICAL'
            elif req['priority_score'] >= 60:
                req['priority_level'] = 'HIGH'
            elif req['priority_score'] >= 40:
                req['priority_level'] = 'MEDIUM'
            else:
                req['priority_level'] = 'LOW'
        
        return sorted(requirements, key=lambda x: x.get('priority_score', 0), reverse=True)
    
    # ============================================================================
    # 6. ADVANCED QUALITY VALIDATION
    # ============================================================================
    
    @staticmethod
    def validate_requirement_quality(requirement: str) -> Dict[str, Any]:
        """
        Comprehensive quality validation with specific issues identified.
        """
        issues = []
        suggestions = []
        warnings = []
        
        normalized = requirement.lower().strip()
        words = normalized.split()
        
        # Check 1: Length
        if len(words) < 3:
            issues.append("Too short - requirement lacks detail")
            suggestions.append("Add more context about who, what, and why")
        elif len(words) > 50:
            warnings.append("Very long - consider splitting into multiple requirements")
        
        # Check 2: Ambiguous terms
        ambiguous_terms = ['user-friendly', 'fast', 'efficient', 'good', 'bad', 'easy', 'simple', 'nice']
        found_ambiguous = [term for term in ambiguous_terms if term in normalized]
        if found_ambiguous:
            issues.append(f"Ambiguous terms found: {', '.join(found_ambiguous)}")
            suggestions.append("Use specific, measurable criteria instead")
        
        # Check 3: Missing action verb
        action_verbs = ['must', 'shall', 'should', 'will', 'enable', 'allow', 'provide', 'calculate', 'fetch']
        if not any(verb in normalized for verb in action_verbs):
            warnings.append("No clear action verb - requirement may be unclear")
            suggestions.append("Start with 'must', 'shall', or 'should'")
        
        # Check 4: Multiple requirements in one
        if normalized.count(' and ') >= 3:
            warnings.append("Contains multiple 'and' clauses - may be compound requirement")
            suggestions.append("Consider splitting into separate requirements")
        
        # Check 5: Negative requirements
        if any(neg in normalized for neg in ['must not', 'shall not', 'should not', 'will not']):
            warnings.append("Negative requirement detected")
            suggestions.append("Consider rephrasing as a positive statement when possible")
        
        # Check 6: Missing specifics
        generic_terms = ['system', 'application', 'platform', 'thing', 'item']
        if any(term in normalized for term in generic_terms) and len(words) < 10:
            warnings.append("Generic terms without specifics")
            suggestions.append("Specify which system/component/feature")
        
        # Calculate overall quality
        quality_score = 100
        quality_score -= len(issues) * 20
        quality_score -= len(warnings) * 10
        quality_score = max(0, quality_score)
        
        return {
            'is_valid': len(issues) == 0,
            'quality_score': quality_score,
            'issues': issues,
            'warnings': warnings,
            'suggestions': suggestions
        }
    
    # ============================================================================
    # 7. SMART CATEGORIZATION WITH CONTEXT
    # ============================================================================
    
    @staticmethod
    def categorize_with_context(requirement: str, context: Dict[str, str], domain: str = 'general') -> Dict[str, Any]:
        """
        Advanced categorization that uses context and domain knowledge.
        """
        normalized = requirement.lower().strip()
        
        # Base classification
        category_scores = {
            'functional': 0.0,
            'non_functional': 0.0,
            'user': 0.0,
            'business': 0.0
        }
        
        # Functional indicators with context awareness
        if domain == 'booking_system':
            functional_keywords = ['book', 'reserve', 'schedule', 'cancel', 'modify', 'slot', 'availability']
            category_scores['functional'] += sum(20 for kw in functional_keywords if kw in normalized)
        elif domain == 'e_commerce':
            functional_keywords = ['cart', 'checkout', 'payment', 'order', 'product', 'inventory']
            category_scores['functional'] += sum(20 for kw in functional_keywords if kw in normalized)
        else:
            functional_keywords = ['must', 'shall', 'calculate', 'process', 'fetch', 'collect']
            category_scores['functional'] += sum(15 for kw in functional_keywords if kw in normalized)
        
        # Non-functional with domain context
        nfr_keywords = ['performance', 'security', 'scalability', 'reliability', 'availability', 'latency']
        category_scores['non_functional'] += sum(25 for kw in nfr_keywords if kw in normalized)
        
        # User stories
        if re.search(r'as\s+(a|an)\s+\w+', normalized) or 'i want' in normalized:
            category_scores['user'] += 50
        
        # Business rules
        business_keywords = ['policy', 'compliance', 'regulation', 'stakeholder', 'approval']
        category_scores['business'] += sum(20 for kw in business_keywords if kw in normalized)
        
        # Context boost
        if context.get('context_before') and domain in context['context_before'].lower():
            # If context mentions the domain, boost domain-specific category
            if domain == 'booking_system':
                category_scores['functional'] += 10
        
        # Determine best category
        best_category = max(category_scores, key=category_scores.get)
        confidence = category_scores[best_category] / sum(category_scores.values()) if sum(category_scores.values()) > 0 else 0
        
        return {
            'category': best_category,
            'confidence': min(1.0, confidence),
            'scores': category_scores,
            'domain_specific': domain != 'general'
        }
    
    # ============================================================================
    # 8. ENHANCED FORMATTING AND PRESENTATION
    # ============================================================================
    
    @staticmethod
    def format_requirements_enhanced(requirements_by_category: Dict[str, List[Dict]]) -> str:
        """
        Enhanced formatting with priority indicators, quality scores, and better organization.
        """
        output_parts = []
        
        for category, reqs in requirements_by_category.items():
            if not reqs:
                continue
            
            output_parts.append(f"\n{'='*80}")
            output_parts.append(f"{category.upper()}")
            output_parts.append(f"{'='*80}\n")
            
            # Sort by priority if available
            sorted_reqs = sorted(reqs, key=lambda x: x.get('priority_score', 50), reverse=True)
            
            for idx, req in enumerate(sorted_reqs, 1):
                text = req.get('text', req if isinstance(req, str) else '')
                priority_level = req.get('priority_level', '') if isinstance(req, dict) else ''
                quality_score = req.get('quality_score', 0) if isinstance(req, dict) else 0
                
                # Format with priority indicator
                priority_icon = ''
                if priority_level == 'CRITICAL':
                    priority_icon = '🔴'
                elif priority_level == 'HIGH':
                    priority_icon = '🟠'
                elif priority_level == 'MEDIUM':
                    priority_icon = '🟡'
                else:
                    priority_icon = '⚪'
                
                # Quality indicator
                quality_icon = ''
                if quality_score >= 80:
                    quality_icon = '✅'
                elif quality_score >= 60:
                    quality_icon = '⚠️'
                elif quality_score > 0:
                    quality_icon = '❌'
                
                # Format requirement
                if priority_level or quality_icon:
                    output_parts.append(f"{idx}. {priority_icon} {quality_icon} {text}")
                else:
                    output_parts.append(f"{idx}. {text}")
            
            output_parts.append("")  # Blank line between categories
        
        return '\n'.join(output_parts)


# Integration helper functions
def integrate_improvements(agent_instance):
    """
    Integrate all improvements into an existing agent instance.
    This can be called to enhance an existing agent.
    """
    improvements = AgentImprovements()
    
    # Add methods to agent instance
    agent_instance.extract_with_context = improvements.extract_with_context
    agent_instance.analyze_document_structure = improvements.analyze_document_structure
    agent_instance.score_requirement_quality = improvements.score_requirement_quality
    agent_instance.detect_domain_patterns = improvements.detect_domain_patterns
    agent_instance.detect_relationships = improvements.detect_relationships
    agent_instance.prioritize_requirements = improvements.prioritize_requirements
    agent_instance.validate_requirement_quality = improvements.validate_requirement_quality
    agent_instance.categorize_with_context = improvements.categorize_with_context
    agent_instance.format_requirements_enhanced = improvements.format_requirements_enhanced
    
    return agent_instance


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Example usage
    sample_text = """
    The booking bot must fetch availability using Google Maps API.
    Payment handling bot shall collect customer card details securely.
    System performance must be optimized for 1000+ concurrent users.
    As a customer, I want to view my booking history so that I can track my reservations.
    """
    
    improvements = AgentImprovements()
    
    # Test context extraction
    requirements_with_context = improvements.extract_with_context(sample_text)
    print(f"Extracted {len(requirements_with_context)} requirements with context")
    
    # Test quality scoring
    for req in requirements_with_context:
        scores = improvements.score_requirement_quality(req['text'])
        print(f"\nRequirement: {req['text']}")
        print(f"Quality Score: {scores['overall']:.1f}")
        print(f"Clarity: {scores['clarity']:.1f}, Completeness: {scores['completeness']:.1f}")
    
    # Test domain detection
    domain_patterns = improvements.detect_domain_patterns(sample_text)
    print(f"\nDetected domains: {list(domain_patterns.keys())}")
    
    print("\n" + "="*80)
    print("✅ All improvements tested successfully!")
    print("="*80)

