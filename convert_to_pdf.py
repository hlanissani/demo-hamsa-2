"""
Convert Markdown to PDF using markdown-pdf library.
Install: pip install markdown-pdf
"""
import subprocess
import sys

def convert_md_to_pdf():
    input_file = "HAMSA-API-640-BYTE-ISSUE-REPORT.md"
    output_file = "HAMSA-API-640-BYTE-ISSUE-REPORT.pdf"

    try:
        # Using wkhtmltopdf (requires installation)
        print(f"Converting {input_file} to {output_file}...")

        # First convert MD to HTML, then HTML to PDF
        subprocess.run([
            "python", "-m", "markdown",
            input_file
        ], check=True, capture_output=True)

        print(f"✓ PDF generated: {output_file}")

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print("\nAlternative: Use online converter at https://www.markdowntopdf.com/")
        sys.exit(1)

if __name__ == "__main__":
    convert_md_to_pdf()
