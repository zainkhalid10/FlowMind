"""Enhanced image summarization service"""
import os
import base64
import requests
from typing import Optional
from collections import Counter


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    val = os.getenv(key, "").lower()
    return val in ("1", "true", "yes", "on")


def enhanced_vlm_summarize(image_path: str, context: str = "", image_type: str = "unknown") -> str:
    """Enhanced VLM summarization with better prompts and fallback handling.
    
    Args:
        image_path: Path to image file
        context: Text context from surrounding document
        image_type: Type of image (diagram, chart, screenshot, etc.)
    
    Returns:
        Summary string or empty if VLM not available
    """
    if not _get_env_bool("FLOWMIND_USE_VLM", False):
        return ""
    
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        
        # Enhanced prompt based on image type and context
        base_prompt = "You are an expert software and business analyst. Analyze this image carefully and provide a detailed, structured summary."
        
        if image_type == "diagram" or "diagram" in context.lower():
            prompt = f"""{base_prompt}
Focus on:
- Architecture components and their relationships
- Data flow and process flows
- User roles and interactions
- System boundaries and interfaces
- Key design patterns or structures

Context from document: {context[:500] if context else "No context available"}

Provide 4-8 bullet points with specific details."""
        
        elif image_type == "chart" or any(word in context.lower() for word in ["chart", "graph", "plot", "data"]):
            prompt = f"""{base_prompt}
Focus on:
- Data trends and patterns
- Key metrics and values
- Comparisons and relationships
- Important insights or conclusions

Context: {context[:500] if context else "No context available"}

Provide 3-6 bullet points with specific data points."""
        
        elif image_type == "workflow" or any(word in context.lower() for word in ["workflow", "process", "state", "transition"]):
            prompt = f"""{base_prompt}
Focus on:
- Process steps and sequence
- Decision points and branches
- States and state transitions
- Actors and their actions
- Entry and exit points

Context: {context[:500] if context else "No context available"}

Provide 4-7 bullet points showing the workflow structure."""
        
        else:
            # Generic enhanced prompt
            prompt = f"""{base_prompt}
Analyze the image content and provide insights about:
- Main subjects and objects
- Relationships and connections
- Key information or data
- Important patterns or structures
- Business or technical implications

Context from document: {context[:500] if context else "No context available"}

Provide 3-6 concise bullet points with actionable insights."""

        models_env = os.getenv("FLOWMIND_VLM_MODELS", "")
        if models_env.strip():
            models = [m.strip() for m in models_env.split(",") if m.strip()]
        else:
            models = [os.getenv("FLOWMIND_OLLAMA_VLM_MODEL", "llava:13b")]
        
        try:
            timeout_ms = int(os.getenv("FLOWMIND_VLM_TIMEOUT_MS", "12000"))  # Increased timeout
        except Exception:
            timeout_ms = 12000

        summaries: list[str] = []
        for model in models:
            try:
                body = {"model": model, "prompt": prompt, "images": [b64], "stream": False}
                resp = requests.post(
                    "http://localhost:11434/api/generate",
                    json=body,
                    timeout=max(2, timeout_ms/1000.0)
                )
                if resp.ok:
                    data = resp.json()
                    txt = (data.get("response") or data.get("output") or "").strip()
                    if txt:
                        summaries.append(txt)
            except Exception as e:
                print(f"VLM model {model} failed: {e}")
                continue

        if not summaries:
            return ""

        # Enhanced merging: better deduplication and ranking
        lines = []
        for s in summaries:
            for ln in (s or "").splitlines():
                ln = (ln or "").strip()
                if not ln or len(ln) < 10:  # Filter very short lines
                    continue
                # Normalize bullets and formatting
                if ln.startswith(("- ", "• ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ")):
                    ln_norm = ln.split(". ", 1)[-1].strip() if ". " in ln else ln[2:].strip()
                else:
                    ln_norm = ln
                if len(ln_norm) > 10:  # Only keep substantial lines
                    lines.append(ln_norm)

        # Count frequency and prioritize common insights
        counts = Counter([l.lower().strip() for l in lines])
        # Prioritize lines that appear in multiple models
        frequent = [(l, counts[l.lower()]) for l in lines if counts[l.lower()] >= 2]
        frequent.sort(key=lambda x: x[1], reverse=True)
        
        seen = set()
        merged = []
        # Add frequent lines first
        for l, _ in frequent:
            k = l.strip().lower()
            if k not in seen and len(k) > 10:
                seen.add(k)
                merged.append(l)
        
        # Add remaining unique lines
        for l in lines:
            k = l.strip().lower()
            if k not in seen and len(k) > 10:
                seen.add(k)
                merged.append(l)
            if len(merged) >= 10:  # Limit to top 10 insights
                break

        if not merged:
            return ""

        header = f"AI Analysis ({len(models)} model{'s' if len(models) > 1 else ''}):" if len(models) > 1 else "AI Analysis:"
        return header + "\n" + "\n".join("• " + m for m in merged[:8])  # Max 8 points
    
    except Exception as e:
        print(f"Enhanced VLM summarize error: {e}")
        return ""


def enhanced_ocr_summarize(ocr_text: str, context: str = "") -> str:
    """Enhanced OCR text summarization with better pattern detection."""
    try:
        raw = (ocr_text or "").strip()
        if not raw:
            return "(no text detected)"
        
        ctx = (context or "").strip()
        lines = [l.strip() for l in (raw + ("\n" + ctx if ctx else "")).splitlines()]
        lines = [l for l in lines if l and len(l) > 2]

        # Enhanced role detection
        role_headers = {
            "student", "employer", "administrator", "evaluator", "admin",
            "user", "manager", "developer", "tester", "analyst", "client",
            "customer", "vendor", "stakeholder"
        }
        
        # Enhanced verb detection
        verbs = (
            "submit", "save", "update", "view", "edit", "approve", "reject",
            "authenticate", "import", "export", "delete", "add", "remove",
            "transfer", "initialize", "set", "resend", "check", "validate",
            "create", "modify", "cancel", "process", "generate", "send",
            "receive", "notify", "assign", "complete", "review", "verify"
        )
        
        # Enhanced infrastructure detection
        infra_nouns = (
            "server", "pc", "database", "sql", "shibboleth", "dns", "web",
            "mail", "system", "api", "service", "application", "module",
            "component", "interface", "gateway", "proxy", "cache"
        )
        
        # Enhanced state detection
        state_terms = {
            "start", "end", "pending", "open", "closed", "saved", "submitted",
            "archived", "completed", "accepted", "rejected", "approved",
            "draft", "active", "inactive", "processing", "failed", "success"
        }

        def is_header(s: str) -> bool:
            t = s.lower().strip(": -")
            return t in role_headers and len(t.split()) <= 2

        def is_action(s: str) -> bool:
            t = s.lower()
            has_verb = any(v in t for v in verbs)
            reasonable_length = 5 <= len(s) <= 100
            return has_verb and reasonable_length

        def is_infrastructure(s: str) -> bool:
            t = s.lower()
            return any(noun in t for noun in infra_nouns)

        def is_state(s: str) -> bool:
            t = s.lower()
            return any(state in t for state in state_terms)

        # Group by role if headers present
        groups = {}
        current_role = None
        any_header = any(is_header(l) for l in lines)
        
        if any_header:
            for l in lines:
                if is_header(l):
                    current_role = l.title()
                    groups.setdefault(current_role, [])
                else:
                    if is_action(l) or is_infrastructure(l) or is_state(l):
                        r = current_role or "General"
                        groups.setdefault(r, []).append(l)
        else:
            # No headers; collect actionable and important lines
            actions = []
            infrastructure = []
            states = []
            seen = set()
            
            for l in lines:
                k = l.strip().lower()
                if k in seen:
                    continue
                seen.add(k)
                
                if is_action(l):
                    actions.append(l)
                elif is_infrastructure(l):
                    infrastructure.append(l)
                elif is_state(l):
                    states.append(l)
            
            if actions:
                groups["Actions"] = actions[:10]
            if infrastructure:
                groups["Infrastructure"] = infrastructure[:8]
            if states:
                groups["States"] = states[:8]

        if not groups:
            # Fallback: return first meaningful lines
            meaningful = [l for l in lines if len(l) > 10][:6]
            if meaningful:
                return "\n".join("• " + m for m in meaningful)
            return "(no structured content detected)"

        # Format output
        output_lines = []
        for role, items in groups.items():
            if items:
                output_lines.append(f"{role}:")
                for item in items[:8]:  # Limit items per group
                    output_lines.append(f"  • {item}")
        
        return "\n".join(output_lines) if output_lines else "(no content)"
    
    except Exception as e:
        print(f"Enhanced OCR summarize error: {e}")
        return (ocr_text or "").strip()[:200] or "(no text)"

