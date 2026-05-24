from pathlib import Path
from PIL import Image
import subprocess

def make_icns():
    project_root = Path(__file__).parent.parent
    png_path = project_root / "assets" / "icon.png"
    iconset_dir = project_root / "assets" / "icon.iconset"
    
    if not png_path.exists():
        print(f"Error: {png_path} not found.")
        return
        
    print(f"Generating macOS iconset from {png_path}...")
    iconset_dir.mkdir(exist_ok=True)
    
    img = Image.open(png_path)
    
    # Standard macOS icon sizes
    sizes = [
        ("16x16", 16),
        ("16x16@2x", 32),
        ("32x32", 32),
        ("32x32@2x", 64),
        ("128x128", 128),
        ("128x128@2x", 256),
        ("256x256", 256),
        ("256x256@2x", 512),
        ("512x512", 512),
        ("512x512@2x", 1024)
    ]
    
    for name, size in sizes:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(iconset_dir / f"icon_{name}.png")
        
    print("Running iconutil to compile .icns...")
    icns_output = project_root / "assets" / "icon.icns"
    try:
        subprocess.run(["iconutil", "-c", "icns", str(iconset_dir)], check=True)
        print(f"✓ Successfully generated: {icns_output}")
    except Exception as e:
        print(f"Error compiling iconset: {e}")
        return
        
    # Clean up iconset directory
    print("Cleaning up temporary iconset files...")
    for f in iconset_dir.glob("*.png"):
        f.unlink()
    iconset_dir.rmdir()
    print("Done!")

if __name__ == "__main__":
    make_icns()
