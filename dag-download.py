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
    description='Download specific files from private Git repository without cloning',
    schedule_interval=None,
    catchup=False,
    tags=['git', 'download'],
)

# Configuration variables
GIT_PAT = "{{ var.value.git_pat }}"  # Store in Airflow Variables
REPO_URL = "{{ var.value.repo_url }}"  # e.g., https://github.com/username/repo or https://github.com/username/repo.git
BRANCH_NAME = "{{ var.value.branch_name }}"  # e.g., main
FILES_PATH = "{{ var.value.files_path }}"  # Comma-separated: path/file1.txt,path/file2.py
DOWNLOAD_FOLDER = "{{ var.value.download_folder }}"  # e.g., /tmp/downloads
IS_BASE64_ENCODED = "{{ var.value.is_base64_encoded }}"  # true or false (for PAT)
ENCODE_FILES_BASE64 = "{{ var.value.encode_files_base64 }}"  # true or false (for downloaded files)

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

echo "=== Starting Git File Download Process (Direct Download - No Clone) ==="
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
REPO_URL_CLEANED=$(echo "$REPO_URL" | sed 's|\.git$||' | sed 's|/$||')

# Detect Git platform and construct raw file URL pattern
if [[ "$REPO_URL_CLEANED" == *"github.com"* ]]; then
    # GitHub: Extract owner and repo
    REPO_INFO=$(echo "$REPO_URL_CLEANED" | sed -E 's|https?://github.com/||')
    PLATFORM="github"
    echo "Platform: GitHub"
elif [[ "$REPO_URL_CLEANED" == *"gitlab"* ]]; then
    # GitLab: Extract project path
    REPO_INFO=$(echo "$REPO_URL_CLEANED" | sed -E 's|https?://[^/]+/||')
    PLATFORM="gitlab"
    echo "Platform: GitLab"
elif [[ "$REPO_URL_CLEANED" == *"bitbucket"* ]]; then
    # Bitbucket: Extract workspace and repo
    REPO_INFO=$(echo "$REPO_URL_CLEANED" | sed -E 's|https?://bitbucket.org/||')
    PLATFORM="bitbucket"
    echo "Platform: Bitbucket"
else
    echo "Error: Unsupported Git platform"
    exit 1
fi

echo "Repository Info: $REPO_INFO"

# Function to download a single file
download_file() {
    local file_path="$1"
    local dest_path="$DOWNLOAD_FOLDER/$file_path"
    
    # Create directory structure
    mkdir -p "$(dirname "$dest_path")"
    
    # Construct raw file URL based on platform
    case "$PLATFORM" in
        github)
            RAW_URL="https://raw.githubusercontent.com/${REPO_INFO}/${BRANCH_NAME}/${file_path}"
            ;;
        gitlab)
            # URL encode the file path for GitLab
            ENCODED_PATH=$(echo "$file_path" | sed 's|/|%2F|g')
            RAW_URL="https://gitlab.com/${REPO_INFO}/-/raw/${BRANCH_NAME}/${file_path}"
            ;;
        bitbucket)
            RAW_URL="https://bitbucket.org/${REPO_INFO}/raw/${BRANCH_NAME}/${file_path}"
            ;;
    esac
    
    echo "Downloading: $file_path"
    echo "URL: $RAW_URL"
    
    # Download file using curl with authentication
    HTTP_CODE=$(curl -s -w "%{http_code}" -H "Authorization: token ${GIT_PAT}" \
                     -H "Accept: application/vnd.github.v3.raw" \
                     -o "/tmp/temp_download_$$" \
                     -L "$RAW_URL")
    
    if [ "$HTTP_CODE" -eq 200 ]; then
        if [ "$ENCODE_FILES_BASE64" = "true" ]; then
            # Encode to base64 and save with .b64 extension
            base64 "/tmp/temp_download_$$" > "${dest_path}.b64"
            echo "✓ Downloaded (Base64): $file_path -> ${file_path}.b64"
        else
            # Move file to destination
            mv "/tmp/temp_download_$$" "$dest_path"
            echo "✓ Downloaded: $file_path"
        fi
        rm -f "/tmp/temp_download_$$"
        return 0
    else
        echo "✗ Failed to download: $file_path (HTTP $HTTP_CODE)"
        rm -f "/tmp/temp_download_$$"
        return 1
    fi
}

# Parse comma-separated file paths and download each file
IFS=',' read -ra FILE_ARRAY <<< "$FILES_PATH"
DOWNLOAD_COUNT=0
FAILED_COUNT=0

for file_path in "${FILE_ARRAY[@]}"; do
    # Trim whitespace
    file_path=$(echo "$file_path" | xargs)
    
    if [ -n "$file_path" ]; then
        if download_file "$file_path"; then
            DOWNLOAD_COUNT=$((DOWNLOAD_COUNT + 1))
        else
            FAILED_COUNT=$((FAILED_COUNT + 1))
        fi
    fi
done

echo ""
echo "=== Download Complete ==="
echo "Total files successfully downloaded: $DOWNLOAD_COUNT"
echo "Total files failed: $FAILED_COUNT"
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

# Exit with error if any downloads failed
if [ "$FAILED_COUNT" -gt 0 ]; then
    exit 1
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
