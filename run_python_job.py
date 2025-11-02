cat > /opt/stonebranch/python/run_python_job.sh << 'EOF'
#!/bin/bash
# StoneBranch Python Job Runner - Dynamic Environment Setup

set -e

JOB_NAME="$1"
REPO_URL="$2"
BRANCH="$3"
PYTHON_VERSION="$4"
MAIN_SCRIPT="$5"
REQUIREMENTS_FILE="$6"
EXTRA_ARGS="$7"

# Generate unique workspace
WORKSPACE="/opt/stonebranch/python/temp/${JOB_NAME}_${UO_TASK_ID}"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# Clone repository
echo "Cloning repository: $REPO_URL (branch: $BRANCH)"
git clone -b "$BRANCH" "$REPO_URL" repo
cd repo

# Validate files exist
if [ ! -f "$MAIN_SCRIPT" ]; then
    echo "ERROR: Main script '$MAIN_SCRIPT' not found in repository"
    exit 1
fi

if [ -n "$REQUIREMENTS_FILE" ] && [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "WARNING: Requirements file '$REQUIREMENTS_FILE' not found, continuing without dependencies"
    REQUIREMENTS_FILE=""
fi

# Execute using Python environment manager
echo "Setting up Python $PYTHON_VERSION environment and executing script"
python3 /opt/stonebranch/python/python_env_manager.py \
    "$PYTHON_VERSION" \
    "$MAIN_SCRIPT" \
    "$REQUIREMENTS_FILE" \
    $EXTRA_ARGS

# Cleanup workspace (optional - keep for debugging)
# cd /
# rm -rf "$WORKSPACE"

echo "Job completed successfully"
EOF

chmod +x /opt/stonebranch/python/run_python_job.sh
