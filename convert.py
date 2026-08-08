import os

# Keep the import at runtime rather than a static `from app import TEMPLATES`.
# This avoids Pyright/Pylance reporting the symbol as an unknown import when
# the app.py module does not expose a typed definition for `TEMPLATES`.
try:
    import app
except ImportError:
    print("Error: Could not import app.py. Make sure this script is in the same folder as app.py.")
    exit(1)

TEMPLATES = getattr(app, "TEMPLATES", None)
if TEMPLATES is None:
    print("Error: Could not find 'TEMPLATES' in app.py. Make sure this script is in the same folder as app.py.")
    exit(1)


def main():
    # 1. Create the templates directory if it doesn't exist
    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"Created directory: {templates_dir}/")

    # 2. Iterate through the dictionary and create the HTML files
    for filename, html_content in TEMPLATES.items():
        filepath = os.path.join(templates_dir, filename)

        # Write the content, stripping leading/trailing whitespace to keep it clean
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content.strip() + "\n")

        print(f"✔️ Extracted: {filepath}")

    print("\n✅ Extraction complete!")
    print("\nNext steps for app.py:")
    print("1. Delete the giant TEMPLATES = { ... } dictionary.")
    print("2. Delete the line: app.jinja_loader = DictLoader(TEMPLATES)")
    print("3. Remove 'DictLoader' from your imports.")
    print("Flask will now automatically route to your new templates/ folder!")


if __name__ == "__main__":
    main()