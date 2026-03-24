import re
from pathlib import Path
from pypdf import PdfReader

PDF_PATHS = [
    Path(r"d:\fyp_phase2\FlowMind\FYP1-FinalReport-F25_387-D-Flowmind.pdf"),
    Path(r"d:\fyp_phase2\FlowMind\uploads\FYP1-FinalReport-F25_387-D-Flowmind.pdf"),
]

KEYWORDS = [
    "technology",
    "technologies",
    "tools",
    "tech stack",
    "framework",
    "frontend",
    "backend",
    "database",
    "ml",
    "ai",
    "python",
    "django",
    "flask",
    "fastapi",
    "react",
    "angular",
    "node",
    "postgres",
    "mysql",
    "mongodb",
    "firebase",
    "opencv",
    "nlp",
    "ocr",
    "pytesseract",
    "langchain",
    "chromadb",
    "transformers",
    "torch",
    "scikit-learn",
    "tensorflow",
    "keras",
    "aws",
    "azure",
    "gcp",
    "sklearn",
    "sqlite",
]

PAT = re.compile("|".join(re.escape(k) for k in KEYWORDS), re.I)

def main():
    pdf_path = next((p for p in PDF_PATHS if p.exists()), None)
    if not pdf_path:
        print("ERROR: Final report PDF not found in expected locations.")
        return

    reader = PdfReader(str(pdf_path))
    print(f"# Source PDF: {pdf_path}")
    print("# Extracted lines mentioning technologies/tools\n")

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines:
            if PAT.search(ln):
                print(f"Page {i:02d}: {ln}")

if __name__ == "__main__":
    main()

