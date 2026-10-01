import json
from pathlib import Path
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import TerminalFormatter

def load_json(file_path):
    """Load JSON data from file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path, indent=4):
    """Save JSON data to file with formatting"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

def print_colored_json(data):
    """Print JSON with colored formatting"""
    try:
        
        json_str = json.dumps(data, indent=4, ensure_ascii=False)
        print(highlight(json_str, JsonLexer(), TerminalFormatter()))
    except ImportError:
        print(json.dumps(data, indent=4, ensure_ascii=False))

# Example usage
if __name__ == "__main__":
    # Load JSON
    input_file = "input.json"
    output_file = "output.json"
    
    data = load_json(input_file)
    
    # Display colored output
    print_colored_json(data)
    
    # Save formatted JSON
    save_json(data, output_file)
    print(f"Saved to {output_file}")