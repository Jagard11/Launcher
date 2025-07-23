from PIL import Image, ImageDraw, ImageFont
import io
import base64
import hashlib
from pathlib import Path

def generate_project_icon(project_name: str, size: int = 128) -> str:
    """Generate a simple square icon with the first letter of the project name"""
    
    # Get first letter, uppercase
    first_letter = project_name[0].upper() if project_name else "?"
    
    # Generate a consistent color based on project name hash
    hash_obj = hashlib.md5(project_name.encode())
    hash_hex = hash_obj.hexdigest()
    
    # Extract RGB values from hash
    r = int(hash_hex[0:2], 16)
    g = int(hash_hex[2:4], 16) 
    b = int(hash_hex[4:6], 16)
    
    # Ensure colors are not too dark or too light
    r = max(50, min(200, r))
    g = max(50, min(200, g))
    b = max(50, min(200, b))
    
    background_color = (r, g, b)
    
    # Create image
    img = Image.new('RGB', (size, size), background_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fallback to default if not available
    try:
        # Try to find a good system font
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/System/Library/Fonts/Helvetica.ttc',  # macOS
            'C:/Windows/Fonts/arial.ttf',  # Windows
        ]
        
        font = None
        font_size = size // 2
        
        for font_path in font_paths:
            if Path(font_path).exists():
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except:
                    continue
        
        if font is None:
            font = ImageFont.load_default()
            
    except:
        font = ImageFont.load_default()
    
    # Calculate text position to center it
    bbox = draw.textbbox((0, 0), first_letter, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Determine text color (white or black) based on background brightness
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    text_color = 'white' if brightness < 128 else 'black'
    
    # Draw the letter
    draw.text((x, y), first_letter, fill=text_color, font=font)
    
    # Add a subtle border
    border_color = tuple(max(0, c - 30) for c in background_color)
    draw.rectangle([0, 0, size-1, size-1], outline=border_color, width=2)
    
    # Convert to base64 string for use in Gradio
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    # Return as data URL
    return f"data:image/png;base64,{img_str}"

def create_icon_file(project_name: str, output_path: str, size: int = 128):
    """Create and save an icon file to disk"""
    icon_data = generate_project_icon(project_name, size)
    
    # Extract base64 data
    base64_data = icon_data.split(',')[1]
    img_data = base64.b64decode(base64_data)
    
    # Save to file
    with open(output_path, 'wb') as f:
        f.write(img_data)

if __name__ == "__main__":
    # Test the icon generator
    test_names = ["ComfyUI", "Stable Diffusion", "Ollama", "Test Project"]
    
    for name in test_names:
        icon = generate_project_icon(name)
        print(f"Generated icon for '{name}': {len(icon)} chars")
        
        # Save test file
        create_icon_file(name, f"test_icon_{name.replace(' ', '_')}.png")
        print(f"Saved test icon for '{name}'") 