import re
import sys

def update_css_in_file(filepath, card_class, image_wrapper_class, info_class, border_radius="12px"):
    """Update CSS in a single file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 1. Remove fixed height from card class
    pattern1 = rf'(\.{card_class}\s*\{{\s*[^}}]*?)height:\s*\d+px;\s*'
    content = re.sub(pattern1, r'\1', content, flags=re.MULTILINE)
    
    # 2. Change .card-container from position: absolute to flexbox
    pattern2 = r'(\.card-container\s*\{)\s*position:\s*absolute;\s*inset:\s*0;'
    replacement2 = r'\1\n                display: flex;\n                flex-direction: column;\n                position: relative;'
    content = re.sub(pattern2, replacement2, content, flags=re.MULTILINE)
    
    # Also handle .card-border if it exists (for pride.html)
    pattern2b = r'(\.card-border\s*\{)\s*position:\s*absolute;\s*inset:\s*0;'
    replacement2b = r'\1\n                display: flex;\n                flex-direction: column;\n                position: relative;'
    content = re.sub(pattern2b, replacement2b, content, flags=re.MULTILINE)
    
    # 3. Change image wrapper from absolute positioning to aspect-ratio
    pattern3 = rf'(\.{image_wrapper_class}\s*\{{)\s*position:\s*absolute;\s*inset:\s*(?:0|3px);'
    replacement3 = rf'\1\n                position: relative;\n                width: 100%;\n                aspect-ratio: 4/3;'
    content = re.sub(pattern3, replacement3, content, flags=re.MULTILINE)
    
    # 4. Add portrait variant class after image wrapper
    # Find the closing brace of the image wrapper class and add portrait variant
    pattern4 = rf'(\.{image_wrapper_class}\s*\{{[^}}]*?\}})'
    def add_portrait(match):
        wrapper_block = match.group(1)
        # Only add if not already present
        if f'.{image_wrapper_class}.portrait' not in content:
            return wrapper_block + f'\n\n            /* Portrait orientation - manually add this class to portrait images */\n            .{image_wrapper_class}.portrait {{\n                aspect-ratio: 3/4;\n            }}'
        return wrapper_block
    content = re.sub(pattern4, add_portrait, content, flags=re.DOTALL)
    
    # 5. Change info overlay from absolute to relative and add flex-shrink
    pattern5 = rf'(\.{info_class}\s*\{{)\s*position:\s*absolute;\s*bottom:\s*0;\s*left:\s*0;\s*right:\s*0;'
    replacement5 = rf'\1\n                position: relative;'
    content = re.sub(pattern5, replacement5, content, flags=re.MULTILINE)
    
    # Add flex-shrink: 0 to info class if not present
    pattern5b = rf'(\.{info_class}\s*\{{[^}}]*?transition:[^;]+;)\s*(\}})'
    def add_flex_shrink(match):
        if 'flex-shrink' not in match.group(0):
            return match.group(1) + '\n                flex-shrink: 0;\n            ' + match.group(2)
        return match.group(0)
    content = re.sub(pattern5b, add_flex_shrink, content, flags=re.DOTALL)
    
    # Remove the .photo-card:hover .photo-image-wrapper { inset: 5px; } rule if present
    pattern6 = rf'\.{card_class}:hover\s+\.{image_wrapper_class}\s*\{{\s*inset:\s*5px;\s*\}}'
    content = re.sub(pattern6, '', content, flags=re.MULTILINE)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Main execution
if __name__ == '__main__':
    if len(sys.argv) < 5:
        print("Usage: python script.py <filepath> <card_class> <image_wrapper_class> <info_class> [border_radius]")
        sys.exit(1)
    
    filepath = sys.argv[1]
    card_class = sys.argv[2]
    image_wrapper_class = sys.argv[3]
    info_class = sys.argv[4]
    border_radius = sys.argv[5] if len(sys.argv) > 5 else "12px"
    
    if update_css_in_file(filepath, card_class, image_wrapper_class, info_class, border_radius):
        print(f"Updated {filepath}")
    else:
        print(f"No changes needed for {filepath}")
