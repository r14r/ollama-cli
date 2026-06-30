import sys
import shutil
import subprocess
from pathlib import Path

def run():
    repo_dir = Path("/Users/Shared/CLOUD/Projekte/CLIs/ollama-cli")
    log_file = repo_dir / "build_out.txt"
    
    with log_file.open("w", encoding="utf-8") as f:
        f.write("Starting build and deploy...\n")
        dist_dir = repo_dir / "dist" / "shiv"
        
        # 1. Clean old shiv dir
        if dist_dir.exists():
            f.write(f"Cleaning {dist_dir}...\n")
            shutil.rmtree(dist_dir)
        dist_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Build shiv package
        shiv_cmd = [
            ".venv/python/bin/shiv",
            "-c", "ollama-cli",
            "-o", str(dist_dir / "ollama-cli.pyz"),
            "."
        ]
        f.write(f"Running shiv command: {' '.join(shiv_cmd)}\n")
        res = subprocess.run(shiv_cmd, cwd=str(repo_dir), capture_output=True, text=True)
        f.write("Shiv STDOUT:\n" + res.stdout + "\n")
        f.write("Shiv STDERR:\n" + res.stderr + "\n")
        if res.returncode != 0:
            f.write("Shiv build failed!\n")
            return
            
        (dist_dir / "build_source.txt").write_text("shiv", encoding="utf-8")
        
        # 3. Deploy
        deploy_target = Path("/Users/Shared/CLOUD/DeveloperTools/bin/ollama-cli")
        f.write(f"Deploying to {deploy_target}...\n")
        shutil.copy2(dist_dir / "ollama-cli.pyz", deploy_target)
        deploy_target.chmod(0o755)
        f.write("Deploy completed successfully!\n")

if __name__ == "__main__":
    run()
