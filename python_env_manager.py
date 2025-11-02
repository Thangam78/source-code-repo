#!/bin/bash
# setup_python_framework.sh

# Create directory structure
mkdir -p /opt/stonebranch/python/onboarding
mkdir -p /opt/stonebranch/python/scripts
mkdir -p /opt/stonebranch/python/logs
mkdir -p /opt/stonebranch/python/temp

# Create main Python environment manager
cat > /opt/stonebranch/python/python_env_manager.py << 'EOF'
#!/usr/bin/env python3
"""
StoneBranch Python Environment Manager
Dynamically creates Python environments based on job requirements
"""

import os
import sys
import json
import subprocess
import hashlib
import logging
from pathlib import Path
import shutil

class PythonEnvManager:
    def __init__(self, config_file=None):
        self.base_dir = Path("/opt/stonebranch/python/onboarding")
        self.setup_logging()
        
        if config_file:
            self.load_config(config_file)
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/opt/stonebranch/python/logs/env_manager.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_config(self, config_file):
        """Load job configuration from JSON"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)
    
    def get_python_installer(self):
        """Download and compile Python from source"""
        install_script = """
#!/bin/bash
PYTHON_VERSION=$1
INSTALL_DIR=$2

cd /tmp
wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz
tar -xzf Python-${PYTHON_VERSION}.tgz
cd Python-${PYTHON_VERSION}

./configure --prefix=${INSTALL_DIR} --enable-optimizations
make -j$(nproc)
make install

# Cleanup
cd /tmp
rm -rf Python-${PYTHON_VERSION}*
"""
        with open('/opt/stonebranch/python/install_python.sh', 'w') as f:
            f.write(install_script)
        os.chmod('/opt/stonebranch/python/install_python.sh', 0o755)
    
    def create_python_environment(self, python_version, requirements_file=None):
        """Create Python environment with specific version"""
        env_hash = hashlib.md5(python_version.encode()).hexdigest()[:8]
        env_dir = self.base_dir / f"python_{python_version}_{env_hash}"
        
        if env_dir.exists():
            self.logger.info(f"Python environment {python_version} already exists at {env_dir}")
            return env_dir
        
        self.logger.info(f"Creating Python {python_version} environment at {env_dir}")
        
        # Install Python if not available
        python_binary = f"/usr/local/bin/python{python_version}"
        if not os.path.exists(python_binary):
            self.logger.info(f"Python {python_version} not found, installing...")
            self.install_python_version(python_version, env_dir)
        else:
            # Create virtual environment using system Python
            subprocess.run([python_binary, "-m", "venv", str(env_dir)], check=True)
        
        # Install requirements if provided
        if requirements_file and os.path.exists(requirements_file):
            self.install_requirements(env_dir, requirements_file)
        
        return env_dir
    
    def install_python_version(self, python_version, install_dir):
        """Install specific Python version"""
        self.logger.info(f"Installing Python {python_version} to {install_dir}")
        
        # Use pyenv for easier Python version management
        cmd = f"""
        curl https://pyenv.run | bash
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
        pyenv install {python_version} -s
        pyenv virtualenv {python_version} stonebranch_{python_version}
        """
        
        try:
            subprocess.run(cmd, shell=True, executable='/bin/bash', check=True)
            # Create symlink to standard location
            venv_path = f"{os.path.expanduser('~')}/.pyenv/versions/{python_version}/envs/stonebranch_{python_version}"
            if os.path.exists(venv_path):
                os.symlink(venv_path, install_dir)
                self.logger.info(f"Python {python_version} installed successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install Python {python_version}: {e}")
            raise
    
    def install_requirements(self, env_dir, requirements_file):
        """Install Python packages from requirements.txt"""
        pip_binary = env_dir / "bin" / "pip"
        if not pip_binary.exists():
            pip_binary = env_dir / "Scripts" / "pip.exe"  # Windows support
        
        cmd = [str(pip_binary), "install", "-r", requirements_file]
        self.logger.info(f"Installing requirements from {requirements_file}")
        
        try:
            subprocess.run(cmd, check=True)
            self.logger.info("Requirements installed successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install requirements: {e}")
            raise
    
    def execute_script(self, env_dir, script_path, *script_args):
        """Execute Python script in the created environment"""
        python_binary = env_dir / "bin" / "python"
        if not python_binary.exists():
            python_binary = env_dir / "Scripts" / "python.exe"
        
        cmd = [str(python_binary), script_path] + list(script_args)
        self.logger.info(f"Executing: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.info("Script executed successfully")
            self.logger.info(f"Output: {result.stdout}")
            return result.returncode
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Script execution failed: {e}")
            self.logger.error(f"Stderr: {e.stderr}")
            raise

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python_env_manager.py <python_version> <script_path> [requirements_file] [args...]")
        sys.exit(1)
    
    python_version = sys.argv[1]
    script_path = sys.argv[2]
    requirements_file = sys.argv[3] if len(sys.argv) > 3 else None
    script_args = sys.argv[4:] if len(sys.argv) > 4 else []
    
    manager = PythonEnvManager()
    
    try:
        env_dir = manager.create_python_environment(python_version, requirements_file)
        return_code = manager.execute_script(env_dir, script_path, *script_args)
        sys.exit(return_code)
    except Exception as e:
        manager.logger.error(f"Job failed: {e}")
        sys.exit(1)
EOF

chmod +x /opt/stonebranch/python/python_env_manager.py
