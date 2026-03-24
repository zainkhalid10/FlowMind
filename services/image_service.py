"""
Enhanced Image Processing Service with Advanced OCR and VLM Integration
"""
import os
import base64
import json
import requests
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from typing import Optional, Dict, List
import re
import io


def sanitize_unicode_text(text: str) -> str:
    """Remove invalid Unicode surrogate characters that can't be encoded to UTF-8."""
    if not text:
        return text
    try:
        # Try to encode to catch surrogates
        text.encode('utf-8')
        return text
    except (UnicodeEncodeError, AttributeError, TypeError):
        # Remove surrogates by encoding with errors='replace' and decoding
        if isinstance(text, str):
            return text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        else:
            text_str = str(text) if text is not None else ""
            return text_str.encode('utf-8', errors='replace').decode('utf-8', errors='replace')


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    val = os.getenv(key, "").lower()
    return val in ("1", "true", "yes", "on")


# ============================================================================
# ADVANCED OCR WITH PREPROCESSING
# ============================================================================

def advanced_ocr_extract(image_path: str) -> Dict[str, str]:
    """
    Advanced OCR with multiple preprocessing techniques for better accuracy.
    Returns dict with 'text' and 'confidence' keys.
    """
    try:
        img = Image.open(image_path)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Try multiple preprocessing strategies
        strategies = [
            ('original', img),
            ('grayscale_enhanced', preprocess_grayscale_enhanced(img)),
            ('binary_adaptive', preprocess_binary_adaptive(img)),
            ('denoised', preprocess_denoise(img))
        ]
        
        best_text = ""
        best_confidence = 0
        
        for strategy_name, processed_img in strategies:
            try:
                # Get OCR with confidence data
                data = pytesseract.image_to_data(processed_img, output_type=pytesseract.Output.DICT)
                
                # Calculate average confidence
                confidences = [int(conf) for conf in data['conf'] if conf != '-1']
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                # Get text
                text_raw = pytesseract.image_to_string(processed_img, config='--psm 6').strip()
                # Sanitize Unicode to remove invalid surrogate characters
                text = sanitize_unicode_text(text_raw)
                
                if len(text) > len(best_text) and avg_confidence >= best_confidence:
                    best_text = text
                    best_confidence = avg_confidence
                    
            except Exception as e:
                continue
        
        return {
            'text': best_text,
            'confidence': best_confidence
        }
    except Exception as e:
        print(f"⚠️  Advanced OCR failed: {e}")
        return {'text': '', 'confidence': 0}


def preprocess_grayscale_enhanced(img: Image.Image) -> Image.Image:
    """Convert to grayscale and enhance contrast."""
    img = img.convert('L')
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    return img


def preprocess_binary_adaptive(img: Image.Image) -> Image.Image:
    """Apply adaptive thresholding for better text detection."""
    img_cv = np.array(img.convert('L'))
    binary = cv2.adaptiveThreshold(
        img_cv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    return Image.fromarray(binary)


def preprocess_denoise(img: Image.Image) -> Image.Image:
    """Denoise image for cleaner text."""
    img_cv = np.array(img.convert('RGB'))
    denoised = cv2.fastNlMeansDenoisingColored(img_cv, None, 10, 10, 7, 21)
    return Image.fromarray(denoised)


# ============================================================================
# INTELLIGENT IMAGE ANALYSIS
# ============================================================================

def detect_image_type_advanced(image_path: str, ocr_text: str) -> Dict[str, any]:
    """
    Advanced image type detection using visual and textual features.
    Returns type, confidence, and characteristics.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {'type': 'unknown', 'confidence': 0, 'characteristics': []}
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        characteristics = []
        type_scores = {
            'diagram': 0,
            'flowchart': 0,
            'chart': 0,
            'table': 0,
            'ui_mockup': 0,
            'text_document': 0,
            'screenshot': 0
        }
        
        # Edge detection for structure
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Line detection
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=50, maxLineGap=10)
        line_count = len(lines) if lines is not None else 0
        
        # Contour detection
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analyze text content
        text_lower = ocr_text.lower()
        
        # Scoring logic
        if line_count > 20:
            type_scores['diagram'] += 30
            type_scores['flowchart'] += 25
            characteristics.append('structured_lines')
        
        if edge_density > 0.1:
            type_scores['diagram'] += 20
            characteristics.append('high_structure')
        
        # Text-based detection
        flowchart_keywords = ['start', 'end', 'decision', 'process', 'if', 'else', 'loop']
        if any(kw in text_lower for kw in flowchart_keywords):
            type_scores['flowchart'] += 40
            characteristics.append('flowchart_keywords')
        
        chart_keywords = ['chart', 'graph', 'data', '%', 'axis', 'plot']
        if any(kw in text_lower for kw in chart_keywords):
            type_scores['chart'] += 35
            characteristics.append('chart_keywords')
        
        table_keywords = ['table', 'row', 'column', '|']
        if any(kw in text_lower for kw in table_keywords) or ocr_text.count('|') > 5:
            type_scores['table'] += 40
            characteristics.append('table_structure')
        
        ui_keywords = ['button', 'menu', 'click', 'field', 'form', 'input']
        if any(kw in text_lower for kw in ui_keywords):
            type_scores['ui_mockup'] += 35
            characteristics.append('ui_elements')
        
        # Text density
        text_ratio = len(ocr_text) / (width * height) if (width * height) > 0 else 0
        if text_ratio > 0.001:
            type_scores['text_document'] += 30
            characteristics.append('text_heavy')
        
        # Rectangle detection for UI/screenshots
        rectangles = [c for c in contours if cv2.contourArea(c) > 1000]
        if len(rectangles) > 5:
            type_scores['ui_mockup'] += 20
            type_scores['screenshot'] += 20
            characteristics.append('multiple_rectangles')
        
        # Determine best type
        best_type = max(type_scores, key=type_scores.get)
        confidence = type_scores[best_type]
        
        return {
            'type': best_type if confidence > 20 else 'unknown',
            'confidence': confidence,
            'characteristics': characteristics,
            'details': {
                'line_count': line_count,
                'edge_density': float(edge_density),
                'contour_count': len(contours),
                'text_length': len(ocr_text)
            }
        }
    except Exception as e:
        print(f"⚠️  Image type detection failed: {e}")
        return {'type': 'unknown', 'confidence': 0, 'characteristics': []}


# ============================================================================
# ENHANCED VLM ANALYSIS
# ============================================================================

def check_ollama_status() -> Dict:
    """Check if Ollama is running and what models are available."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=2.0)
        if resp.ok:
            data = resp.json()
            models = [m.get('name', '') for m in data.get('models', [])]
            return {
                'running': True,
                'models': models,
                'has_vlm': any('llava' in m.lower() or 'vision' in m.lower() for m in models)
            }
    except Exception as e:
        return {
            'running': False,
            'error': str(e),
            'models': []
        }
    
    return {'running': False, 'models': []}


def _try_vlm_model(model: str, b64: str, prompt: str, ollama_models: list, vlm_timeout: float) -> str:
    """Try a single VLM model. Returns interpretation string or empty."""
    if model not in ollama_models:
        print(f"   ⚠️  Model '{model}' not in Ollama, skipping")
        return ""
    try:
        test_img = Image.new('RGB', (5, 5), color='red')
        test_buf = io.BytesIO()
        test_img.save(test_buf, format='PNG')
        test_b64 = base64.b64encode(test_buf.getvalue()).decode()
        test_resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": "OK", "images": [test_b64], "stream": False,
                  "options": {"num_predict": 5, "temperature": 0.1}},
            timeout=15
        )
        if not test_resp.ok:
            return ""
    except Exception:
        return ""
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 500, "num_ctx": 2048, "repeat_penalty": 1.1}
        },
        timeout=vlm_timeout
    )
    if resp.ok:
        result = resp.json().get("response", "").strip()
        return result if result else ""
    return ""


def enhanced_vlm_analyze(image_path: str, ocr_text: str, image_type: str, context: str = "") -> Dict:
    """
    Enhanced VLM analysis with smart prompts based on image type and context.
    Supports FLOWMIND_VLM_MODELS (comma-separated) for hybrid Qwen2.5-VL and LLaVA-13B.
    Returns comprehensive interpretation.
    """
    if not _get_env_bool("FLOWMIND_USE_VLM", False):
        print("   ⚠️  VLM disabled in .env (FLOWMIND_USE_VLM=false)")
        return {
            'interpretation': '',
            'requirements': [],
            'components': [],
            'confidence': 0
        }
    
    # Check Ollama status
    ollama_status = check_ollama_status()
    if not ollama_status['running']:
        print(f"   ❌ Ollama is not running! Error: {ollama_status.get('error', 'Connection failed')}")
        print(f"   💡 Start Ollama with: ollama serve")
        return {
            'interpretation': '',
            'requirements': [],
            'components': [],
            'confidence': 0
        }
    
    # Support FLOWMIND_VLM_MODELS (qwen2.5-vl,llava:13b) or single FLOWMIND_OLLAMA_VLM_MODEL
    vlm_models_str = os.getenv("FLOWMIND_VLM_MODELS", "").strip()
    if vlm_models_str:
        models = [m.strip() for m in vlm_models_str.split(",") if m.strip()]
    else:
        models = [os.getenv("FLOWMIND_OLLAMA_VLM_MODEL", "llava:13b")]
    
    ollama_models = ollama_status.get('models', [])
    available = [m for m in models if m in ollama_models]
    if not available:
        print(f"   ❌ No VLM models found. Tried: {models}")
        print(f"   📦 Available: {', '.join(ollama_models) if ollama_models else 'None'}")
        print(f"   💡 Install with: ollama pull qwen2.5-vl  or  ollama pull llava:13b")
        return {
            'interpretation': '',
            'requirements': [],
            'components': [],
            'confidence': 0
        }
    
    print(f"   🤖 Using VLM models: {', '.join(available)}")
    
    vlm_timeout = float(os.getenv("FLOWMIND_VLM_TIMEOUT", "60.0"))
    vlm_enabled = os.getenv("FLOWMIND_USE_VLM", "true").lower() == "true"
    if not vlm_enabled:
        print(f"   ⚠️  VLM is disabled (FLOWMIND_USE_VLM=false), skipping VLM analysis")
        return {'interpretation': '', 'requirements': [], 'components': [], 'confidence': 0}
    
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
            image_size_mb = len(image_data) / (1024 * 1024)
            if image_size_mb > 10:
                print(f"   ⚠️  Large image detected ({image_size_mb:.1f} MB) - processing may take longer")
            b64 = base64.b64encode(image_data).decode('utf-8')
        
        prompt = build_smart_prompt(image_type, ocr_text, context)
        
        print(f"   📤 Sending image to VLM... (timeout: {vlm_timeout}s per model)")
        interpretations = []
        for model in available:
            print(f"   🔍 Trying model: {model}")
            result = _try_vlm_model(model, b64, prompt, ollama_models, vlm_timeout)
            if result:
                interpretations.append((model, result))
                print(f"   ✅ {model}: {len(result)} chars")
            else:
                print(f"   ⚠️  {model}: no response or failed")
        
        if not interpretations:
            print(f"   ⚠️  All VLM models failed or returned empty")
            return {'interpretation': '', 'requirements': [], 'components': [], 'confidence': 0}
        
        # Merge interpretations: concatenate with separator, deduplicate lines
        merged = "\n\n---\n\n".join(r for _, r in interpretations)
        seen_lines = set()
        deduped_lines = []
        for line in merged.split("\n"):
            line_stripped = line.strip()
            key = line_stripped.lower()
            if key and key not in seen_lines:
                seen_lines.add(key)
                deduped_lines.append(line)
        merged = "\n".join(deduped_lines)
        
        print(f"   ✅ VLM analysis complete ({len(merged)} chars from {len(interpretations)} model(s))")
        parsed = parse_vlm_response(merged, image_type)
        return {
            'interpretation': merged,
            'requirements': parsed.get('requirements', []),
            'components': parsed.get('components', []),
            'relationships': parsed.get('relationships', []),
            'confidence': 85
        }
            
    except requests.exceptions.Timeout:
        print(f"   ⏱️  VLM request timed out after {vlm_timeout}s")
        print(f"   💡 Set FLOWMIND_USE_VLM=false or FLOWMIND_VLM_TIMEOUT=120 in .env")
    except Exception as e:
        print(f"   ❌ VLM analysis exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return {'interpretation': '', 'requirements': [], 'components': [], 'confidence': 0}


def build_smart_prompt(image_type: str, ocr_text: str, context: str) -> str:
    """Build intelligent prompts based on image type."""
    
    base = f"""You are analyzing a {image_type} image from a software requirements document.

Context: {context[:200] if context else 'Software requirements specification'}
OCR extracted text: "{ocr_text[:300] if ocr_text else 'No text detected'}"

"""
    
    type_specific_prompts = {
        'flowchart': """This is a flowchart/process diagram. Analyze and extract:
1. PROCESS STEPS: List each step/node in the flowchart in order
2. DECISION POINTS: Identify decision branches and conditions
3. START/END POINTS: Note the beginning and end states
4. REQUIREMENTS: Extract any functional requirements implied by the flow
5. BUSINESS LOGIC: Describe the business rules shown

Format your response clearly with these sections.""",

        'diagram': """This is a system diagram. Analyze and extract:
1. COMPONENTS: List all system components/modules shown
2. CONNECTIONS: Describe how components are connected
3. DATA FLOWS: Identify data flowing between components
4. ARCHITECTURE: Describe the overall architecture pattern
5. TECHNICAL REQUIREMENTS: Extract any technical constraints or requirements

Be specific about component names and relationships.""",

        'chart': """This is a data chart/graph. Analyze and extract:
1. CHART TYPE: Identify the type (bar, line, pie, etc.)
2. DATA CATEGORIES: List the categories or dimensions shown
3. KEY METRICS: Identify the metrics being measured
4. INSIGHTS: Describe key trends or patterns visible
5. REQUIREMENTS: Extract any performance or data requirements implied

Focus on quantitative information.""",

        'table': """This is a table/matrix. Analyze and extract:
1. TABLE STRUCTURE: Describe rows and columns
2. HEADERS: List column headers and row labels
3. KEY DATA: Extract important data points or values
4. RELATIONSHIPS: Describe relationships between data
5. REQUIREMENTS: Extract any requirements specified in the table

Be thorough with data extraction.""",

        'ui_mockup': """This is a UI mockup/wireframe. Analyze and extract:
1. UI ELEMENTS: List all visible UI components (buttons, fields, menus)
2. LAYOUT: Describe the screen layout and organization
3. USER INTERACTIONS: Identify possible user actions
4. NAVIGATION: Describe navigation flow if visible
5. FUNCTIONAL REQUIREMENTS: Extract UI-related requirements

Be detailed about interactive elements.""",

        'screenshot': """This is a screenshot. Analyze and extract:
1. APPLICATION CONTEXT: Identify what application/system this is
2. VISIBLE FEATURES: List all visible features and functions
3. USER INTERFACE: Describe the UI layout and components
4. CURRENT STATE: Describe what state/action is shown
5. REQUIREMENTS: Extract any requirements visible

Focus on functional aspects.""",

        'text_document': """This is a text document. Analyze and extract:
1. MAIN CONTENT: Summarize the key text content
2. REQUIREMENTS: Extract any explicit requirements statements
3. SPECIFICATIONS: Identify technical specifications
4. CONSTRAINTS: Note any constraints or limitations mentioned
5. KEY POINTS: List the most important points

Be comprehensive with text extraction."""
    }
    
    specific_prompt = type_specific_prompts.get(image_type, 
        """Analyze this image and extract:
1. MAIN SUBJECT: What is shown in the image
2. KEY ELEMENTS: Important components or elements
3. TEXT CONTENT: Any visible text or labels
4. REQUIREMENTS: Any requirements implied or stated
5. TECHNICAL DETAILS: Technical information visible

Provide detailed analysis.""")
    
    return base + specific_prompt


def parse_vlm_response(response: str, image_type: str) -> Dict:
    """Parse structured information from VLM response."""
    parsed = {
        'requirements': [],
        'components': [],
        'relationships': []
    }
    
    # Extract requirements (looking for must/shall/should statements)
    req_patterns = [
        r'(?:must|shall|should|will|need to)\s+([^.!?\n]+)',
        r'requirement[s]?:\s*([^.!?\n]+)',
        r'system\s+(?:must|shall|should)\s+([^.!?\n]+)'
    ]
    
    for pattern in req_patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        parsed['requirements'].extend(matches)
    
    # Extract components (for diagrams)
    if image_type in ['diagram', 'flowchart']:
        component_patterns = [
            r'component[s]?:\s*([^.!?\n]+)',
            r'module[s]?:\s*([^.!?\n]+)',
            r'(?:include|contain)[s]?\s+([A-Z][^.!?,\n]+)'
        ]
        for pattern in component_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            parsed['components'].extend(matches)
    
    # Extract relationships
    relation_keywords = ['connect', 'link', 'flow', 'interact', 'communicate']
    for keyword in relation_keywords:
        pattern = f'{keyword}[s]?\\s+([^.!?\n]+)'
        matches = re.findall(pattern, response, re.IGNORECASE)
        parsed['relationships'].extend(matches)
    
    # Clean and deduplicate
    parsed['requirements'] = list(set([r.strip() for r in parsed['requirements'] if len(r.strip()) > 10]))
    parsed['components'] = list(set([c.strip() for c in parsed['components'] if len(c.strip()) > 3]))
    parsed['relationships'] = list(set([r.strip() for r in parsed['relationships'] if len(r.strip()) > 10]))
    
    return parsed


# ============================================================================
# COMPREHENSIVE IMAGE INTERPRETATION
# ============================================================================

def comprehensive_image_interpretation(image_path: str, context: str = "") -> Dict:
    """
    Complete image interpretation combining OCR, VLM, and analysis.
    This is the main function to use for image interpretation.
    """
    print(f"🖼️  Comprehensive interpretation: {os.path.basename(image_path)}")
    
    # Step 1: Advanced OCR
    ocr_result = advanced_ocr_extract(image_path)
    ocr_text = ocr_result['text']
    ocr_confidence = ocr_result['confidence']
    
    print(f"   📝 OCR: {len(ocr_text)} chars (confidence: {ocr_confidence:.1f}%)")
    
    # Step 2: Detect image type
    type_info = detect_image_type_advanced(image_path, ocr_text)
    image_type = type_info['type']
    
    print(f"   🔍 Type: {image_type} (confidence: {type_info['confidence']})")
    
    # Step 3: VLM analysis (if enabled)
    vlm_result = {'interpretation': '', 'requirements': [], 'components': [], 'relationships': []}
    
    if _get_env_bool("FLOWMIND_USE_VLM", False):
        print(f"   🤖 Starting VLM analysis...")
        vlm_result = enhanced_vlm_analyze(image_path, ocr_text, image_type, context)
        if vlm_result.get('interpretation'):
            print(f"   ✅ VLM: {len(vlm_result['interpretation'])} chars")
        else:
            print(f"   ⚠️  VLM analysis produced no results (falling back to OCR-only)")
    else:
        print(f"   ⏭️  VLM disabled, using intelligent OCR analysis")
    
    # Step 4: Merge and structure results
    final_interpretation = merge_interpretations(
        ocr_text, 
        ocr_confidence,
        vlm_result,
        type_info
    )
    
    print(f"   ✅ Complete: {len(final_interpretation['full_interpretation'])} chars")
    
    return final_interpretation


def intelligent_ocr_analysis(ocr_text: str, image_type: str) -> Dict:
    """
    Intelligent analysis of OCR text to extract structured information.
    This works WITHOUT VLM and provides detailed interpretation.
    """
    analysis = {
        'summary': '',
        'requirements': [],
        'components': [],
        'process_steps': [],
        'key_points': []
    }
    
    if not ocr_text or len(ocr_text) < 20:
        return analysis
    
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
    
    # Analyze based on image type
    if image_type in ['flowchart', 'diagram']:
        # Extract process steps and components
        analysis['summary'] = f"This {image_type} shows a workflow with {len(lines)} identifiable elements."
        
        for line in lines:
            line_lower = line.lower()
            
            # Identify requirements
            if any(word in line_lower for word in ['must', 'shall', 'should', 'will', 'need', 'require']):
                analysis['requirements'].append(line)
            
            # Identify steps (numbered or action verbs)
            if re.match(r'^\d+[.:]?\s+', line) or any(verb in line_lower for verb in ['validate', 'extract', 'convert', 'process', 'perform', 'generate', 'store', 'upload', 'parse']):
                analysis['process_steps'].append(line)
            
            # Identify components (capitalized words, technical terms)
            if re.search(r'[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*', line):
                components = re.findall(r'[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*', line)
                analysis['components'].extend([c for c in components if len(c) > 3])
        
        # Deduplicate components
        analysis['components'] = list(set(analysis['components']))[:10]
        
    elif image_type == 'table':
        analysis['summary'] = f"This table contains structured data with {len(lines)} rows."
        # Extract key data points
        for line in lines:
            if ':' in line or '|' in line:
                analysis['key_points'].append(line)
    
    else:
        # General analysis
        analysis['summary'] = f"This image contains text content with {len(lines)} lines."
        # Extract important lines (longer ones, or with keywords)
        important = [l for l in lines if len(l) > 30 or any(kw in l.lower() for kw in ['system', 'user', 'data', 'process', 'requirement'])]
        analysis['key_points'] = important[:10]
    
    return analysis


def merge_interpretations(ocr_text: str, ocr_confidence: float, vlm_result: Dict, type_info: Dict) -> Dict:
    """Intelligently merge OCR and VLM results into comprehensive interpretation."""
    
    sections = []
    image_type = type_info['type']
    
    # Image type and characteristics
    sections.append(f"**Image Type**: {image_type.replace('_', ' ').title()}")
    if type_info.get('characteristics'):
        sections.append(f"**Characteristics**: {', '.join(type_info['characteristics'])}")
    
    # Intelligent OCR analysis (works without VLM)
    ocr_analysis = intelligent_ocr_analysis(ocr_text, image_type)
    
    # Summary
    if ocr_analysis.get('summary'):
        sections.append(f"\n**Analysis**:")
        sections.append(ocr_analysis['summary'])
    
    # OCR text (show condensed version)
    if ocr_text and len(ocr_text) > 50:
        sections.append(f"\n**Text Content** (Confidence: {ocr_confidence:.0f}%):")
        # Show structured or condensed version
        if len(ocr_text) > 500:
            sections.append(ocr_text[:500] + "...")
        else:
            sections.append(ocr_text)
    
    # Process steps (for flowcharts/algorithms)
    if ocr_analysis.get('process_steps'):
        sections.append(f"\n**Process Steps**:")
        for i, step in enumerate(ocr_analysis['process_steps'][:15], 1):
            sections.append(f"{i}. {step}")
    
    # VLM interpretation (if available)
    if vlm_result.get('interpretation'):
        sections.append(f"\n**Visual Analysis**:")
        sections.append(vlm_result['interpretation'])
    
    # Requirements (from both OCR and VLM)
    all_requirements = list(set(ocr_analysis.get('requirements', []) + vlm_result.get('requirements', [])))
    if all_requirements:
        sections.append(f"\n**Requirements Identified**:")
        for i, req in enumerate(all_requirements[:10], 1):
            sections.append(f"{i}. {req}")
    
    # Components (from both sources)
    all_components = list(set(ocr_analysis.get('components', []) + vlm_result.get('components', [])))
    if all_components:
        sections.append(f"\n**Key Components**:")
        sections.append(", ".join(all_components[:15]))
    
    # Key points
    if ocr_analysis.get('key_points') and not ocr_analysis.get('process_steps'):
        sections.append(f"\n**Key Information**:")
        for point in ocr_analysis['key_points'][:8]:
            sections.append(f"• {point}")
    
    # Relationships (from VLM)
    if vlm_result.get('relationships'):
        sections.append(f"\n**Relationships**:")
        for rel in vlm_result['relationships'][:5]:
            sections.append(f"• {rel}")
    
    # Technical details
    if image_type in ['flowchart', 'diagram']:
        details = []
        if type_info.get('details', {}).get('line_count', 0) > 20:
            details.append(f"Contains {type_info['details']['line_count']} structural lines")
        if len(ocr_analysis.get('process_steps', [])) > 0:
            details.append(f"{len(ocr_analysis['process_steps'])} identifiable steps")
        if len(all_components) > 0:
            details.append(f"{len(all_components)} components/modules")
        
        if details:
            sections.append(f"\n**Technical Details**: {', '.join(details)}")
    
    full_interpretation = "\n".join(sections)
    
    return {
        'full_interpretation': full_interpretation,
        'ocr_text': ocr_text,
        'ocr_confidence': ocr_confidence,
        'image_type': type_info['type'],
        'vlm_interpretation': vlm_result.get('interpretation', ''),
        'requirements': all_requirements,
        'components': all_components,
        'relationships': vlm_result.get('relationships', []),
        'process_steps': ocr_analysis.get('process_steps', []),
        'quality_score': calculate_interpretation_quality(ocr_text, vlm_result, type_info)
    }


def calculate_interpretation_quality(ocr_text: str, vlm_result: Dict, type_info: Dict) -> int:
    """Calculate quality score (0-100) for the interpretation."""
    score = 0
    
    # OCR quality
    if len(ocr_text) > 50:
        score += 20
    elif len(ocr_text) > 10:
        score += 10
    
    # Type detection confidence
    score += min(type_info.get('confidence', 0) / 3, 25)
    
    # VLM content richness
    if vlm_result.get('interpretation'):
        interp_len = len(vlm_result['interpretation'])
        if interp_len > 200:
            score += 25
        elif interp_len > 100:
            score += 15
        elif interp_len > 50:
            score += 10
    
    # Structured data extraction
    if vlm_result.get('requirements'):
        score += min(len(vlm_result['requirements']) * 5, 15)
    if vlm_result.get('components'):
        score += min(len(vlm_result['components']) * 3, 10)
    if vlm_result.get('relationships'):
        score += min(len(vlm_result['relationships']) * 2, 5)
    
    return min(score, 100)


# ============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ============================================================================

def enhanced_vlm_summarize(image_path: str, context: str = "", image_type: str = "unknown") -> str:
    """Legacy function - returns simple string summary."""
    result = comprehensive_image_interpretation(image_path, context)
    return result['full_interpretation']


def enhanced_ocr_summarize(ocr_text: str, context: str = "") -> str:
    """Legacy function - processes raw OCR text."""
    if not ocr_text or len(ocr_text.strip()) < 10:
        return "(no text detected)"
    
    lines = [l.strip() for l in ocr_text.splitlines() if l.strip() and len(l.strip()) > 2]
    
    # Group by patterns
    role_headers = {'student', 'employer', 'admin', 'user', 'manager', 'customer'}
    action_verbs = ['submit', 'save', 'update', 'view', 'edit', 'approve', 'create', 'delete']
    
    def is_header(s): 
        return s.lower().strip(': -') in role_headers
    
    def is_action(s): 
        return any(v in s.lower() for v in action_verbs) and 5 <= len(s) <= 100
    
    groups = {}
    current_role = None
    
    for line in lines:
        if is_header(line):
            current_role = line.title()
            groups.setdefault(current_role, [])
        elif is_action(line):
            role = current_role or "Actions"
            groups.setdefault(role, []).append(line)
    
    if not groups:
        meaningful = [l for l in lines if len(l) > 10][:6]
        return '\n'.join('• ' + m for m in meaningful) if meaningful else ocr_text[:200]
    
    output = []
    for role, items in groups.items():
        if items:
            output.append(f"{role}:")
            for item in items[:8]:
                output.append(f"  • {item}")
    
    return '\n'.join(output) if output else ocr_text[:200]


def fast_extract_image(image_path: str, image_id: str) -> Dict:
    """Fast OCR extraction for upload phase."""
    ocr_result = advanced_ocr_extract(image_path)
    type_info = detect_image_type_advanced(image_path, ocr_result['text'])
    
    return {
        'image_id': image_id,
        'image_path': image_path,
        'ocr_text': ocr_result['text'],
        'ocr_confidence': ocr_result['confidence'],
        'image_type': type_info['type'],
        'has_text': len(ocr_result['text']) > 10,
        'characteristics': type_info.get('characteristics', [])
    }
