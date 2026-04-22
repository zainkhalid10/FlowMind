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
from typing import Optional, Dict, List, Any, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _is_vlm_pass_enabled() -> bool:
    """
    Centralized VLM-pass toggle for image processing.
    Uses FLOWMIND_IMAGE_REQ_VLM_PASS and prints runtime value for debugging.
    """
    vlm_pass = os.getenv("FLOWMIND_IMAGE_REQ_VLM_PASS", "1")
    print(f"VLM_PASS_ENV_VALUE: {vlm_pass}")
    vlm_enabled = vlm_pass.strip() == "1"
    print(f"VLM_ENABLED: {vlm_enabled}")
    return vlm_enabled


def _resolve_vlm_models(ollama_models: List[str]) -> List[str]:
    """
    Resolve preferred VLM models from env + installed Ollama tags.
    Prefers stronger open-source vision models for diagrams/flowcharts.
    """
    configured = os.getenv("FLOWMIND_VLM_MODELS", "").strip()
    if configured:
        requested = [m.strip() for m in configured.split(",") if m.strip()]
    else:
        # Prefer Qwen2.5-VL first for diagram semantics, then LLaVA fallback.
        requested = [
            os.getenv("FLOWMIND_OLLAMA_VLM_MODEL", "").strip(),
            "qwen2.5-vl",
            "qwen2.5-vl:latest",
            "qwen2.5vl:latest",
            "llava:13b",
            "llava:latest",
            "llava:7b",
        ]

    requested = [m for m in requested if m]
    if not requested:
        requested = ["qwen2.5-vl", "llava:13b"]

    aliases = {
        "qwen2.5-vl": ["qwen2.5-vl", "qwen2.5-vl:latest", "qwen2.5vl:latest"],
        "llava": ["llava:13b", "llava:latest", "llava:7b"],
    }

    available: List[str] = []
    seen = set()
    installed = set(ollama_models or [])

    for model in requested:
        candidates = aliases.get(model, [model])
        chosen = next((c for c in candidates if c in installed), None)
        if chosen and chosen not in seen:
            available.append(chosen)
            seen.add(chosen)

    return available


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
            'er_diagram': 0,
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

        horizontal_lines = 0
        vertical_lines = 0
        if lines is not None:
            for ln in lines:
                x1, y1, x2, y2 = ln[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > dy * 2:
                    horizontal_lines += 1
                elif dy > dx * 2:
                    vertical_lines += 1

        quadrilateral_count = 0
        rectangle_count = 0
        diamond_count = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 250:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
            if len(approx) == 4:
                quadrilateral_count += 1
                rect = cv2.minAreaRect(contour)
                rw, rh = rect[1]
                if rw <= 1 or rh <= 1:
                    continue
                aspect = max(rw, rh) / max(1.0, min(rw, rh))
                angle = abs(rect[2])
                if 0.75 <= aspect <= 1.35 and 20 <= angle <= 70:
                    diamond_count += 1
                else:
                    rectangle_count += 1
        
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
        
        # Check for flowchart BEFORE checking table.
        # If image has both rectangles and diamonds, this strongly indicates flowchart.
        if diamond_count > 0:
            type_scores['flowchart'] += 45
            characteristics.append('diamond_decisions')
        if diamond_count > 0 and rectangle_count > 0:
            type_scores['flowchart'] += 35
            characteristics.append('mixed_rectangles_and_diamonds')
        elif diamond_count >= 2:
            type_scores['flowchart'] += 20

        has_grid_pattern = horizontal_lines >= 6 and vertical_lines >= 6
        if has_grid_pattern:
            type_scores['table'] += 35
            characteristics.append('grid_lines')

        table_keywords = ['table', 'row', 'column', '|']
        if any(kw in text_lower for kw in table_keywords) or ocr_text.count('|') > 5:
            type_scores['table'] += 40
            characteristics.append('table_structure')

        er_keywords = [
            'entity', 'relationship', 'primary key', 'foreign key',
            'varchar', 'char(', 'int', 'pk', 'fk'
        ]
        er_hits = sum(1 for kw in er_keywords if kw in text_lower)
        if er_hits >= 2:
            type_scores['er_diagram'] += 45
            type_scores['table'] -= 15
            characteristics.append('database_schema_terms')
        if rectangle_count >= 3 and (horizontal_lines + vertical_lines) >= 3 and diamond_count == 0:
            type_scores['er_diagram'] += 20
            characteristics.append('entity_boxes_with_connectors')
        
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
                'text_length': len(ocr_text),
                'horizontal_lines': horizontal_lines,
                'vertical_lines': vertical_lines,
                'rectangle_count': rectangle_count,
                'diamond_count': diamond_count,
                'quadrilateral_count': quadrilateral_count,
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
    if not _is_vlm_pass_enabled():
        print("   ⚠️  VLM disabled via FLOWMIND_IMAGE_REQ_VLM_PASS")
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
    
    ollama_models = ollama_status.get('models', [])
    available = _resolve_vlm_models(ollama_models)
    if not available:
        print(f"   ❌ No VLM models found. Installed: {', '.join(ollama_models) if ollama_models else 'None'}")
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
    if not _is_vlm_pass_enabled():
        print("   ⚠️  VLM is disabled (FLOWMIND_IMAGE_REQ_VLM_PASS!=1), skipping VLM analysis")
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
        print(f"   💡 Set FLOWMIND_IMAGE_REQ_VLM_PASS=0 or FLOWMIND_VLM_TIMEOUT=120 in .env")
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
        'flowchart': f"""{_diagram_understanding_preamble()}
This is a flowchart from a requirements document. Complete Step 1 using the image and this context:
{(context or '')[:1000]}

For Step 2, list each major path or branch as a SHALL-style requirement where possible, with evidence
(decision diamond text, arrow labels). Pay special attention to: numeric limits (e.g. retries),
error handling paths, blocking conditions.
""",

        'diagram': f"""{_diagram_understanding_preamble()}
This is a system / architecture diagram. Complete Step 1 using the image.

For Step 2, be specific about component names, interfaces, data flows, trust boundaries, and constraints
implied by how parts are connected. Where possible, phrase as SHALL requirements with evidence (box labels, arrows).
""",

        'er_diagram': f"""{_diagram_understanding_preamble()}
This is an ER/database schema diagram. Complete Step 1 using the image and OCR labels.

For Step 2, extract:
- entities/tables and their attributes
- primary/foreign keys and inferred cardinality
- integrity constraints and required validations
Express each as SHALL requirements with direct evidence from labels/links.
""",

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
    
    if _is_vlm_pass_enabled():
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
        
    elif image_type == 'er_diagram':
        analysis['summary'] = "This appears to be a database/ER diagram with entities, attributes, and relationships."
        for line in lines:
            line_lower = line.lower()
            if any(token in line_lower for token in ['int', 'varchar', 'char', 'primary key', 'foreign key', 'pk', 'fk']):
                analysis['components'].append(line)
            if re.search(r'\b(one|many|1:n|n:1|m:n)\b', line_lower):
                analysis['key_points'].append(line)
        analysis['components'] = list(set(analysis['components']))[:12]

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
    
    # OCR text (show condensed version). Suppress noisy dumps for structured visuals.
    is_structured_visual = image_type in ['flowchart', 'diagram', 'er_diagram']
    has_vlm = bool((vlm_result.get('interpretation') or "").strip())
    show_ocr_dump = bool(
        ocr_text
        and len(ocr_text) > 50
        and (
            (not is_structured_visual)
            or (is_structured_visual and ocr_confidence >= 60 and len(ocr_text) <= 400)
        )
    )
    if show_ocr_dump:
        sections.append(f"\n**Text Content** (Confidence: {ocr_confidence:.0f}%):")
        # Show structured or condensed version
        if len(ocr_text) > 500:
            sections.append(ocr_text[:500] + "...")
        else:
            sections.append(ocr_text)
    elif is_structured_visual and ocr_text:
        labels = []
        seen = set()
        for raw in ocr_text.splitlines():
            line = re.sub(r"\s+", " ", (raw or "").strip())
            if len(line) < 3 or len(line) > 80:
                continue
            if not re.search(r"[A-Za-z]", line):
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            labels.append(line)
            if len(labels) >= 8:
                break
        if labels:
            sections.append("\n**Detected Labels (OCR)**:")
            sections.append(", ".join(labels))
    
    # Process steps (for flowcharts/algorithms)
    if ocr_analysis.get('process_steps'):
        sections.append(f"\n**Process Steps**:")
        for i, step in enumerate(ocr_analysis['process_steps'][:15], 1):
            sections.append(f"{i}. {step}")
    
    # VLM interpretation (if available) — tag diagrams for RAG / extraction
    if vlm_result.get('interpretation'):
        interp = (vlm_result.get('interpretation') or "").strip()
        if image_type in ('diagram', 'flowchart', 'er_diagram'):
            sections.append("\n[DIAGRAM_UNDERSTANDING]")
            sections.append(
                "Narrative understanding of the figure (use when drafting or validating requirements):"
            )
            sections.append(interp)
            sections.append("[/DIAGRAM_UNDERSTANDING]")
        else:
            sections.append(f"\n**Visual Analysis**:")
            sections.append(interp)
    
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
    if image_type in ['flowchart', 'diagram', 'er_diagram']:
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


def should_run_vlm_requirements_pass(image: Union[Image.Image, str, None], ocr_text: str) -> bool:
    """Skip icons, banners, and text-heavy tables; run VLM on likely diagrams."""
    try:
        if isinstance(image, str):
            if not image or not os.path.exists(image):
                return False
            image = Image.open(image)
        if image is None:
            return False
        w, h = image.size
        if w < 100 or h < 100:
            return False
        if w > h * 4:
            return False
        if len((ocr_text or "").strip()) > 300:
            return False
        return True
    except Exception:
        return False


def detect_scenario(before_text: str, after_text: str, ocr_text: str) -> str:
    has_local_text = (
        len((before_text or "").strip()) > 30
        or len((after_text or "").strip()) > 30
    )
    has_ocr_text = len((ocr_text or "").strip()) > 20
    if not has_local_text and not has_ocr_text:
        return "diagram_only"
    if has_local_text:
        return "diagram_with_local_text"
    return "diagram_with_context"


def split_page_text_around_image(
    page_text: str, image_index_on_page: int, total_images_on_page: int
) -> tuple:
    """Approximate text immediately before / after an image on a page."""
    pt = page_text or ""
    if not pt.strip():
        return "", ""
    n = max(1, total_images_on_page)
    idx = max(1, min(image_index_on_page, n))
    L = len(pt)
    slot = L / n
    boundary = int((idx - 0.5) * slot)
    before = pt[max(0, boundary - 500):boundary]
    after = pt[boundary:min(L, boundary + 500)]
    return before[-500:], after[:500]


def get_image_context(
    before_text: str,
    after_text: str,
    ocr_text: str,
    image_index: int,
    page_number: int,
) -> Dict[str, Any]:
    surrounding_text = f"{(before_text or '')[-500:]}\n{(after_text or '')[:500]}".strip()
    return {
        "before_text": (before_text or "")[-500:],
        "after_text": (after_text or "")[:500],
        "surrounding_document_text": surrounding_text[:1000],
        "image_index": image_index,
        "page_number": page_number,
        "scenario": detect_scenario(before_text, after_text, ocr_text),
    }


def classify_diagram_type(image_path: str) -> Dict[str, Any]:
    """
    Classify diagram type using OpenCV shape detection.

    Returns:
    {
      type: flowchart/table/architecture/state_diagram/er_diagram/unknown,
      confidence: 0-100,
      detected_features: [list]
    }
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {
                "type": "unknown",
                "confidence": 30,
                "detected_features": ["unrecognized pattern"],
            }

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        diamonds = 0
        rectangles = 0
        circles = 0
        oval_like = 0

        for cnt in contours:
            if cv2.contourArea(cnt) < 200:
                continue
            perimeter = cv2.arcLength(cnt, True)
            if perimeter <= 0:
                continue
            approx = cv2.approxPolyDP(cnt, 0.04 * perimeter, True)
            sides = len(approx)

            if sides == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect = (float(w) / float(h)) if h > 0 else 0.0
                # Square-like rotated boxes are commonly decisions / diamond candidates.
                if 0.8 < aspect < 1.2:
                    diamonds += 1
                else:
                    rectangles += 1
            elif sides > 8:
                circles += 1
                x, y, w, h = cv2.boundingRect(cnt)
                aspect = (float(w) / float(h)) if h > 0 else 0.0
                # Treat stretched circles as oval-like (use-case / ER cues).
                if 1.25 < aspect < 2.8 or 0.35 < aspect < 0.8:
                    oval_like += 1

        # Detect line orientation for table/grid and connection hints.
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=100, minLineLength=50, maxLineGap=10
        )
        horizontal = 0
        vertical = 0
        if lines is not None:
            for ln in lines:
                x1, y1, x2, y2 = ln[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > dy * 2:
                    horizontal += 1
                elif dy > dx * 2:
                    vertical += 1
        has_grid = horizontal >= 6 and vertical >= 6
        has_connectors = (horizontal + vertical) >= 5

        detected_features: List[str] = []
        if diamonds:
            detected_features.append(f"{diamonds} decision nodes found")
        if rectangles:
            detected_features.append(f"{rectangles} rectangular cells/boxes found")
        if circles:
            detected_features.append(f"{circles} circular nodes found")
        if oval_like:
            detected_features.append(f"{oval_like} oval nodes found")
        if has_grid:
            detected_features.append("grid of lines detected")
        if has_connectors:
            detected_features.append("connecting lines detected")

        if diamonds >= 2:
            return {
                "type": "flowchart",
                "confidence": 80,
                "detected_features": detected_features or [f"{diamonds} decision nodes found"],
            }
        if has_grid and rectangles > 6 and circles == 0:
            return {
                "type": "table",
                "confidence": 75,
                "detected_features": detected_features or [f"{rectangles} rectangular cells found"],
            }
        if circles >= 3:
            return {
                "type": "state_diagram",
                "confidence": 70,
                "detected_features": detected_features or [f"{circles} circular nodes found"],
            }
        if oval_like >= 2:
            return {
                "type": "er_diagram",
                "confidence": 68,
                "detected_features": detected_features or [f"{oval_like} oval nodes found"],
            }
        if rectangles >= 3 and diamonds == 0:
            return {
                "type": "architecture",
                "confidence": 65,
                "detected_features": detected_features or [f"{rectangles} component boxes found"],
            }
        return {
            "type": "unknown",
            "confidence": 30,
            "detected_features": detected_features or ["unrecognized pattern"],
        }
    except Exception as e:
        print(f"classify_diagram_type failed: {e}")
        return {"type": "unknown", "confidence": 30, "detected_features": ["unrecognized pattern"]}


def _diagram_understanding_preamble() -> str:
    """Instructions the VLM must follow before listing formal REQUIREMENT lines."""
    return """STEP 1 — UNDERSTANDING (write this FIRST, before any "REQUIREMENT:" lines):
You must explain what the diagram means, not only list bullets.

### 1. PLAIN_LANGUAGE_EXPLANATION
Write 4–8 sentences as if briefing a product analyst who cannot see the image: what process or structure is shown,
who or what participates, and what outcome or control the diagram is meant to convey.

### 2. STRUCTURED_UNDERSTANDING
Use bullet sub-headings (fill from the visual; write "unknown" only if truly not visible):
- Primary purpose:
- Main sequence or control flow (ordered steps):
- Actors / swimlanes / subsystems / stores:
- Decisions, guards, or branches:
- Data or control exchanged between parts:
- Error paths, loops, or alternate flows (if any):

### 3. IMPLIED_BEHAVIORS_FOR_IMPLEMENTATION
List 3–10 short bullets: concrete behaviors an engineer would need to implement so the system matches the diagram
(still plain language; modal verbs optional).

STEP 2 — FORMAL REQUIREMENTS (after Step 1 is complete):
"""


def _extract_understanding_from_diagram_vlm(merged: str) -> str:
    """Pull narrative understanding from a diagram VLM response for RAG / downstream extraction."""
    if not merged or not str(merged).strip():
        return ""
    text = str(merged).strip()
    m = re.search(
        r"(?ims)STEP\s*1[^\n]*\n(.*)(?=^\s*STEP\s*2|^\s*REQUIREMENT:\s*)",
        text,
    )
    if m:
        block = m.group(1).strip()
        if len(block) >= 10:
            return block[:12000]
    m = re.search(
        r"(?ims)(###\s*1\.?\s*PLAIN[^\n]*\n.*?)(?=^\s*###\s*REQUIREMENT|^\s*REQUIREMENT:\s*|^\s*STEP\s*2)",
        text,
    )
    if m:
        block = m.group(1).strip()
        if len(block) >= 10:
            return block[:12000]
    m2 = re.search(r"(?im)^REQUIREMENT:\s*", text)
    if m2 and m2.start() >= 12:
        prefix = text[: m2.start()].strip()
        # Drop duplicate Step-1 header line if present (keep narrative only).
        lines = prefix.splitlines()
        if lines and re.match(r"(?i)^STEP\s*1\b", lines[0].strip()):
            prefix = "\n".join(lines[1:]).strip()
        if len(prefix) >= 10:
            return prefix[:12000]
    if len(text) > 200 and "NO_REQUIREMENTS_FOUND" not in text.upper():
        return text[:4000]
    return ""


def _build_type_specific_diagram_prompt(diagram_type: str, surrounding_document_text: str) -> str:
    """
    Type-specific prompts per architecture spec:
    flowchart / table / architecture / state_diagram / unknown.
    """
    surrounding = (surrounding_document_text or "").strip()[:1000]
    preamble = _diagram_understanding_preamble()
    if diagram_type == "flowchart":
        body = """This is a flowchart. Analyze the complete flow step by step.

What is the starting condition or trigger?
List every decision point and both outcomes (yes/no or true/false)
What loops exist and what condition breaks them?
What are all the end states?
What happens on the error or failure path?
Convert each path into a SHALL requirement. A flowchart with a login attempt limit means:
The system SHALL block access after N failed attempts."""
    elif diagram_type == "table":
        body = """This is a data table. Analyze its structure.

What entity does this table represent?
What are the column headers and what do they mean?
What relationships or constraints does this table show?
Convert the table structure into system requirements about data storage and retrieval."""
    elif diagram_type == "architecture":
        body = """This is a system architecture diagram. Analyze the components.

List every component or module shown
What does each component do based on its label?
What connections exist between components?
What data flows between them?
Convert each component and connection into a system requirement."""
    elif diagram_type == "state_diagram":
        body = """This is a state diagram. Analyze all states and transitions.

List every state shown
What triggers each transition between states?
What are the initial and final states?
Convert each state and transition into a system requirement using SHALL language."""
    elif diagram_type == "er_diagram":
        body = """This is an ER/database schema diagram. Analyze entities and constraints.

List each entity/table and key attributes
Identify primary keys and foreign keys
Infer relationships and cardinality where visible
Note validation and integrity rules implied by keys/types
Convert schema relationships into system/data requirements."""
    else:
        body = """Analyze this technical diagram carefully.

What type of diagram is this?
What system or process does it describe?
What behaviors, constraints, or rules does it show?
Extract any implied system requirements using SHALL/MUST language."""

    return f"""{preamble}
{body}

Surrounding document text:
{surrounding}
"""


def _build_scenario_vlm_prompt(
    scenario: str,
    before_text: str,
    after_text: str,
    ocr_text: str,
    diagram_type: str = "diagram",
    surrounding_document_text: str = "",
) -> str:
    type_prompt = _build_type_specific_diagram_prompt(diagram_type, surrounding_document_text)
    req_base = """After Step 1 is complete, for EACH formal requirement output EXACTLY:
REQUIREMENT: [The system shall ...]
CATEGORY: [Functional / Non-Functional / Business / System]
PRIORITY: [High / Medium / Low]
EVIDENCE: [specific visual element, label, or arrow supporting this]

Only extract what is directly evidenced. No invention.
If no formal requirements can be grounded after Step 1, still complete Step 1, then output: NO_REQUIREMENTS_FOUND
(and do not fabricate REQUIREMENT lines).
"""
    req_with_src_dt = req_base.replace(
        "EVIDENCE:",
        "SOURCE: [diagram / text / both]\nEVIDENCE:",
        1,
    )
    req_with_src_ocr = req_base.replace(
        "EVIDENCE:",
        "SOURCE: [diagram / ocr_text / both]\nEVIDENCE:",
        1,
    )
    if scenario == "diagram_only":
        return f"""You are a requirements analyst examining a technical diagram
from a Software Requirements Specification document.
This diagram has no surrounding text — you must derive
everything from the visual content alone.

{type_prompt}

In Step 1, look for: flows between components, decision points, actors, data stores, system boundaries,
and what they imply for system behavior (explain before you formalize).

{req_base}"""

    if scenario == "diagram_with_local_text":
        return f"""You are a requirements analyst examining a technical diagram
from a Software Requirements Specification document.

The diagram has accompanying text. Use BOTH the diagram
and the text together. Ground Step 1 in the visual; use text to disambiguate labels and intent.
Text before diagram: {before_text[:1200]}
Text after diagram: {after_text[:1200]}

{type_prompt}

{req_with_src_dt}"""

    # diagram_with_context
    ocr_snip = (ocr_text or "")[:1200]
    return f"""You are a requirements analyst examining a technical diagram
from a Software Requirements Specification document.

OCR extracted this text from or near the image:
{ocr_snip}

Use the OCR text as labels/caption context alongside the visual diagram.

{type_prompt}

{req_with_src_ocr}"""


def _parse_vlm_requirement_blocks(merged: str) -> List[str]:
    """Extract requirement blocks from VLM output (REQUIREMENT: lines)."""
    if not merged:
        return []
    blocks: List[str] = []
    current: List[str] = []
    for line in merged.splitlines():
        line = line.rstrip()
        if re.match(r"(?i)^REQUIREMENT:\s*", line):
            if current:
                blocks.append("\n".join(current).strip())
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    if not blocks:
        for line in merged.splitlines():
            m = re.match(r"(?i)^REQUIREMENT:\s*(.+)$", line.strip())
            if m and m.group(1).strip():
                blocks.append(line.strip())
    out: List[str] = []
    seen = set()
    for b in blocks:
        b = sanitize_unicode_text(b.strip())
        if len(b) < 12:
            continue
        key = re.sub(r"\s+", " ", b.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out[:25]


def extract_diagram_requirements_vlm(
    image_path: str,
    scenario: str,
    before_text: str = "",
    after_text: str = "",
    ocr_text: str = "",
) -> Dict[str, Any]:
    """
    Scenario-aware VLM pass: narrative diagram understanding plus formal REQUIREMENT blocks.
    Returns {"requirements": [...], "understanding": "...", "diagram_info": {...}}.
    """
    empty = {
        "requirements": [],
        "understanding": "",
        "diagram_info": {"type": "unknown", "confidence": 30, "detected_features": ["unrecognized pattern"]},
    }
    if not _is_vlm_pass_enabled():
        return empty
    if not image_path or not os.path.exists(image_path):
        return empty
    ollama_status = check_ollama_status()
    if not ollama_status.get("running"):
        return empty
    ollama_models = ollama_status.get("models", [])
    available = _resolve_vlm_models(ollama_models)
    if not available:
        return empty

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        vlm_timeout = float(os.getenv("FLOWMIND_VLM_TIMEOUT", "60.0"))
        surrounding_document_text = f"{(before_text or '')[-500:]}\n{(after_text or '')[:500]}".strip()
        diagram_info = classify_diagram_type(image_path)
        diagram_type = str(diagram_info.get("type") or "unknown")
        print(f"DIAGRAM_TYPE_CLASSIFIED: {diagram_type} ({diagram_info.get('confidence', 0)}%)")
        prompt = _build_scenario_vlm_prompt(
            scenario,
            before_text,
            after_text,
            ocr_text,
            diagram_type=diagram_type,
            surrounding_document_text=surrounding_document_text,
        )
        responses: List[str] = []
        for model in available:
            out = _try_vlm_model(model, b64, prompt, ollama_models, vlm_timeout)
            if out:
                responses.append(out)
                break
        if not responses:
            return empty
        merged = "\n".join(responses)
        understanding = _extract_understanding_from_diagram_vlm(merged)
        reqs = _parse_vlm_requirement_blocks(merged)
        if not reqs and "NO_REQUIREMENTS_FOUND" in merged.upper():
            reqs = []
        return {
            "requirements": reqs,
            "understanding": understanding.strip(),
            "diagram_info": diagram_info,
        }
    except Exception as e:
        print(f"extract_diagram_requirements_vlm failed: {e}")
        return empty


def extract_testable_requirements_from_image(image_path: str, context: str = "") -> List[str]:
    """
    Backward-compatible wrapper: single-image pass using diagram_with_context
    when OCR/context exists, else diagram_only.
    """
    ocr_result = advanced_ocr_extract(image_path) if image_path and os.path.exists(image_path) else {}
    ocr_text = (ocr_result or {}).get("text", "") or ""
    scenario = "diagram_with_context" if len(ocr_text.strip()) > 20 else "diagram_only"
    pack = extract_diagram_requirements_vlm(
        image_path,
        scenario,
        before_text=context[:500] if context else "",
        after_text="",
        ocr_text=ocr_text,
    )
    if isinstance(pack, dict):
        return list(pack.get("requirements") or [])
    return []


def run_parallel_diagram_vlm_jobs(
    jobs: List[Dict[str, Any]],
    max_workers: int = 3,
) -> List[Dict[str, Any]]:
    """
    Run per-image VLM extraction concurrently (max_workers typically 3 for Ollama stability).
    Each job: image_path, image_id, page_num, ocr_text, context (dict from get_image_context).
    """
    if not jobs:
        return []

    def _one(job: Dict[str, Any]) -> Dict[str, Any]:
        image_path = job.get("image_path", "")
        image_id = job.get("image_id", "")
        page_num = job.get("page_num", 0)
        ocr_text = job.get("ocr_text", "") or ""
        ctx = job.get("context") or {}
        scenario = ctx.get("scenario", "diagram_with_context")
        try:
            pil = Image.open(image_path) if image_path and os.path.exists(image_path) else None
        except Exception:
            pil = None
        if not should_run_vlm_requirements_pass(pil or image_path, ocr_text):
            diagram_info = classify_diagram_type(image_path) if image_path else {
                "type": "unknown",
                "confidence": 30,
                "detected_features": ["unrecognized pattern"],
            }
            return {
                "image_id": image_id,
                "page_num": page_num,
                "requirements": [],
                "requirements_count": 0,
                "diagram_info": diagram_info,
                "vlm_analysis": "",
                "skipped": True,
            }
        pack = extract_diagram_requirements_vlm(
            image_path,
            scenario,
            before_text=ctx.get("before_text", ""),
            after_text=ctx.get("after_text", ""),
            ocr_text=ocr_text,
        )
        reqs = list((pack or {}).get("requirements") or [])
        understanding = str((pack or {}).get("understanding") or "").strip()
        diagram_info = (pack or {}).get("diagram_info") or {
            "type": "unknown",
            "confidence": 30,
            "detected_features": ["unrecognized pattern"],
        }
        return {
            "image_id": image_id,
            "page_num": page_num,
            "requirements": reqs,
            "requirements_count": len(reqs),
            "understanding": understanding,
            "diagram_info": diagram_info,
            "vlm_analysis": understanding,
            "skipped": False,
        }

    max_workers = max(1, min(int(max_workers), 3, len(jobs)))
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_one, j): j for j in jobs}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                print(f"Image VLM job failed: {e}")
    return results


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
