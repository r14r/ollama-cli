import subprocess
from pathlib import Path
import traceback

log_file = Path('/Users/Shared/CLOUD/Projekte/CLIs/ollama-cli/version_test_out.txt')

try:
    log_file.write_text("Script started...\n", encoding='utf-8')
    res = subprocess.run(['/Users/Shared/CLOUD/DeveloperTools/bin/ollama-cli', '--version'], capture_output=True, text=True)
    output = f"OUT: {repr(res.stdout)}\nERR: {repr(res.stderr)}\n"
    log_file.write_text(output, encoding='utf-8')
except Exception as e:
    err_msg = f"ERROR: {str(e)}\n{traceback.format_exc()}"
    log_file.write_text(err_msg, encoding='utf-8')
