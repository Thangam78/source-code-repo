from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'download_files_from_private_repo',
    default_args=default_args,
    description='Download files from private Git repository',
    schedule_interval=None,
    catchup=False,
    tags=['git', 'download'],
)

# Configuration variables
GIT_PAT = "{{ var.value.git_pat }}"  # Store in Airflow Variables
REPO_URL = "{{ var.value.repo_url }}"  # e.g., https://github.com/username/repo.git
BRANCH_NAME = "{{ var.value.branch_name }}"  # e.g., main
FILES_PATH = "{{ var.value.files_path }}"  # Comma-separated: path/file1.txt,path/file2.py
DOWNLOAD_FOLDER = "{{ var.value.download_folder }}"  # e.g., /tmp/downloads
IS_BASE64_ENCODED = "{{ var.value.is_base64_encoded }}"  # true or false
ENCODE_FILES_BASE64 = "{{ var.value.encode_files_base64 }}"  # true or false

bash_script = """
#!/bin/bash
set -e

# Input parameters
GIT_PAT="{{ params.git_pat }}"
REPO_URL="{{ params.repo_url }}"
BRANCH_NAME="{{ params.branch_name }}"
FILES_PATH="{{ params.files_path }}"
DOWNLOAD_FOLDER="{{ params.download_folder }}"
IS_BASE64_ENCODED="{{ params.is_base64_encoded }}"
ENCODE_FILES_BASE64="{{ params.encode_files_base64 }}"

echo "=== Starting Git File Download Process ==="
echo "Repository: $REPO_URL"
echo "Branch: $BRANCH_NAME"
echo "Download Folder: $DOWNLOAD_FOLDER"
echo "Encode files to Base64: $ENCODE_FILES_BASE64"

# Decode PAT if it's base64 encoded
if [ "$IS_BASE64_ENCODED" = "true" ]; then
    echo "Decoding Base64 encoded PAT..."
    GIT_PAT=$(echo "$GIT_PAT" | base64 -d)
fi

# Create download folder if it doesn't exist
mkdir -p "$DOWNLOAD_FOLDER"

# Extract repo details from URL
REPO_URL_CLEANED=$(echo "$REPO_URL" | sed 's|\.git$||')
REPO_HOST=$(echo "$REPO_URL_CLEANED" | sed -E 's|https?://||' | cut -d'/' -f1)
REPO_PATH=$(echo "$REPO_URL_CLEANED" | sed -E 's|https?://[^/]+/||')

echo "Repository Host: $REPO_HOST"
echo "Repository Path: $REPO_PATH"

# Create authenticated URL
AUTH_URL="https://${GIT_PAT}@${REPO_HOST}/${REPO_PATH}.git"

# Create a temporary directory for cloning
TEMP_DIR=$(mktemp -d)
echo "Temporary directory: $TEMP_DIR"

# Cleanup function
cleanup() {
    echo "Cleaning up temporary directory..."
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Clone the repository with sparse checkout
echo "Initializing sparse checkout..."
cd "$TEMP_DIR"
git init
git remote add origin "$AUTH_URL"
git config core.sparseCheckout true

# Parse comma-separated file paths and add to sparse-checkout
IFS=',' read -ra FILE_ARRAY <<< "$FILES_PATH"
for file_path in "${FILE_ARRAY[@]}"; do
    # Trim whitespace
    file_path=$(echo "$file_path" | xargs)
    echo "$file_path" >> .git/info/sparse-checkout
    echo "Added to sparse-checkout: $file_path"
done

# Pull only the specified branch and files
echo "Pulling files from branch: $BRANCH_NAME"
git pull origin "$BRANCH_NAME"

# Copy downloaded files to the destination folder
echo "Copying files to destination folder..."
DOWNLOAD_COUNT=0
for file_path in "${FILE_ARRAY[@]}"; do
    file_path=$(echo "$file_path" | xargs)
    if [ -f "$file_path" ]; then
        # Create directory structure in destination
        FILE_DIR=$(dirname "$file_path")
        mkdir -p "$DOWNLOAD_FOLDER/$FILE_DIR"
        
        # Determine destination file path
        DEST_FILE="$DOWNLOAD_FOLDER/$file_path"
        
        # Copy or encode file based on configuration
        if [ "$ENCODE_FILES_BASE64" = "true" ]; then
            # Encode file content to base64 and save with .b64 extension
            base64 "$file_path" > "${DEST_FILE}.b64"
            echo "✓ Downloaded (Base64): $file_path -> ${file_path}.b64"
        else
            # Copy file as-is
            cp "$file_path" "$DEST_FILE"
            echo "✓ Downloaded: $file_path"
        fi
        
        DOWNLOAD_COUNT=$((DOWNLOAD_COUNT + 1))
    else
        echo "✗ File not found: $file_path"
    fi
done

echo "=== Download Complete ==="
echo "Total files downloaded: $DOWNLOAD_COUNT"
echo "Files location: $DOWNLOAD_FOLDER"

# List downloaded files
echo ""
echo "Downloaded files:"
find "$DOWNLOAD_FOLDER" -type f

# If files were encoded, show how to decode
if [ "$ENCODE_FILES_BASE64" = "true" ]; then
    echo ""
    echo "Note: Files are Base64 encoded with .b64 extension"
    echo "To decode a file, use: base64 -d <filename>.b64 > <filename>"
fi
"""

download_task = BashOperator(
    task_id='download_files_from_git',
    bash_command=bash_script,
    params={
        'git_pat': GIT_PAT,
        'repo_url': REPO_URL,
        'branch_name': BRANCH_NAME,
        'files_path': FILES_PATH,
        'download_folder': DOWNLOAD_FOLDER,
        'is_base64_encoded': IS_BASE64_ENCODED,
        'encode_files_base64': ENCODE_FILES_BASE64,
    },
    dag=dag,
)

download_task
