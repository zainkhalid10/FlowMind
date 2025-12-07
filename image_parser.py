import cv2
import pytesseract
from PIL import Image

# Path to your test image
image_path = "diagram.png"   # put a diagram image in same folder

# Load image
img = cv2.imread(image_path)

# Convert to grayscale
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Apply thresholding to improve OCR
gray = cv2.threshold(gray, 0, 255,
                     cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

# OCR with Tesseract
text = pytesseract.image_to_string(gray)

print("📄 Extracted Text from Image:")
print(text)

# Detect contours (shapes)
contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"🖼 Detected {len(contours)} shapes in the image.")
