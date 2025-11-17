#!/bin/bash
set -euo pipefail

# -------------------------------
# INPUTS
# -------------------------------
REPO_URL="https://github.com/ORG/REPO.git"
GITHUB_PAT="YOUR_PERSONAL_ACCESS_TOKEN"

# Comma-separated file paths to download from the repo
FILE_PATHS="path/to/file1.py,path/to/dir/file2.json"

# Branch or commit SHA
REF="main"

# Local directory to store downloaded files
TARGET_ROOT="./downloaded_repo"
mkdir -p "$TARGET_ROOT"

# -------------------------------
# Parse repo owner and repo name
# -------------------------------
REPO_OWNER=$(echo "$REPO_URL" | awk -F/ '{print $(NF-1)}')
REPO_NAME=$(echo "$REPO_URL" | awk -F/ '{print $NF}' | sed 's/.git$//')

echo "Repo Owner : $REPO_OWNER"
echo "Repo Name  : $REPO_NAME"
echo "Saving to  : $TARGET_ROOT"
echo "----------------------------------------"

IFS=',' read -ra FILE_LIST <<< "$FILE_PATHS"

# -------------------------------
# Download each file
# -------------------------------
for REL_PATH in "${FILE_LIST[@]}"; do
    REL_PATH="$(echo "$REL_PATH" | xargs)"  # trim whitespace

    if [[ -z "$REL_PATH" ]]; then
        continue
    fi

    TARGET_DIR="$TARGET_ROOT/$(dirname "$REL_PATH")"
    mkdir -p "$TARGET_DIR"

    RAW_URL="https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/contents/$REL_PATH?ref=$REF"

    echo "Downloading: $REL_PATH"
    
    RESPONSE=$(curl -s -H "Authorization: token $GITHUB_PAT" "$RAW_URL")

    # Use python to decode the Base64 "content" field
    python3 - "$TARGET_DIR/$REL_PATH" <<EOF <<< "$RESPONSE"
import sys, json, base64, os

resp = json.loads(sys.stdin.read())
outfile = sys.argv[1]

if 'message' in resp:
    print(f"ERROR: {resp['message']}", file=sys.stderr)
    sys.exit(1)

content = resp.get("content")
if not content:
    print("ERROR: No content found", file=sys.stderr)
    sys.exit(1)

data = base64.b64decode(content)

os.makedirs(os.path.dirname(outfile), exist_ok=True)
with open(outfile, "wb") as f:
    f.write(data)
EOF

    if [[ ! -f "$TARGET_DIR/$REL_PATH" ]]; then
        echo "ERROR: Failed to download $REL_PATH"
        exit 1
    fi

    echo "✔ Saved to $TARGET_DIR/$REL_PATH"
done

echo "----------------------------------------"
echo "Download completed successfully!"
