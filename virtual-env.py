
#!/bin/bash
# File: /opt/stonebranch/scripts/python_job_wrapper_dynamic.sh
# Purpose: Universal wrapper with dynamic Python version management

set -e

# ==========================================
# CONFIGURATION VARIABLES (From UAC Task)
# ==========================================
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"  # e.g., 3.8, 3.9, 3.10, 3.11, 3.12
GIT_REPO_URL="${GIT_REPO_URL}"
GIT_BRANCH="${GIT_BRANCH:-main}"
SCRIPT_PATH="${SCRIPT_PATH}"
SCRIPT_ARGS="${SCRIPT_ARGS:-}"
TEAM_NAME="${TEAM_NAME}"
APP_NAME="${APP_NAME}"
JOB_NAME="${JOB_NAME}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements.txt}"
GIT_TOKEN="${GIT_TOKEN}"
ADDITIONAL_PACKAGES="${ADDITIONAL_PACKAGES:-}"  # Space-separated list

# ==========================================
# INTERNAL VARIABLES
# ==========================================
BASE_DIR="/opt/stonebranch"
REPO_DIR="${BASE_DIR}/repos/${TEAM_NAME}/${APP_NAME}"
VENV_DIR="${BASE_DIR}/venvs/${TEAM_NAME}_${APP_NAME}_py${PYTHON_VERSION}"
LOG_DIR="${BASE_DIR}/logs/${TEAM_NAME}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/${APP_NAME}_${JOB_NAME}_${TIMESTAMP}.log"

# Create log directory if doesn't exist
mkdir -p ${LOG_DIR}

# ==========================================
# LOGGING FUNCTIONS
# ==========================================
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1" | tee -a ${LOG_FILE}
}

error_exit() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" | tee -a ${LOG_FILE}
    exit 1
}

warning() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] $1" | tee -a ${LOG_FILE}
}

# ==========================================
# VALIDATION
# ==========================================
log "=========================================="
log "Python Job Execution Started"
log "=========================================="
log "Team: ${TEAM_NAME}"
log "Application: ${APP_NAME}"
log "Job: ${JOB_NAME}"
log "Python Version: ${PYTHON_VERSION}"
log "Repository: ${GIT_REPO_URL}"
log "Branch: ${GIT_BRANCH}"
log "Script: ${SCRIPT_PATH}"
log "=========================================="

# Validate required variables
if [ -z "${GIT_REPO_URL}" ]; then
    error_exit "GIT_REPO_URL is required"
fi

if [ -z "${SCRIPT_PATH}" ]; then
    error_exit "SCRIPT_PATH is required"
fi

if [ -z "${TEAM_NAME}" ] || [ -z "${APP_NAME}" ] || [ -z "${JOB_NAME}" ]; then
    error_exit "TEAM_NAME, APP_NAME, and JOB_NAME are required"
fi

# ==========================================
# VIRTUAL ENVIRONMENT SETUP
# ==========================================
log "Checking virtual environment: ${VENV_DIR}"

if [ ! -d "${VENV_DIR}" ]; then
    log "Virtual environment not found. Creating new environment with Python ${PYTHON_VERSION}"
    
    # Check if system Python version exists
    PYTHON_CMD="python${PYTHON_VERSION}"
    
    if ! command -v ${PYTHON_CMD} &> /dev/null; then
        error_exit "Python ${PYTHON_VERSION} is not installed on this system. Please contact platform team to install Python ${PYTHON_VERSION}"
    fi
    
    log "Using Python: $(${PYTHON_CMD} --version)"
    
    # Create virtual environment
    ${PYTHON_CMD} -m venv ${VENV_DIR} || error_exit "Failed to create virtual environment"
    
    log "Virtual environment created successfully"
else
    log "Virtual environment already exists"
fi

# Activate virtual environment
log "Activating virtual environment"
source ${VENV_DIR}/bin/activate || error_exit "Failed to activate virtual environment"

# Verify Python version in venv
ACTIVE_PYTHON_VERSION=$(python --version 2>&1)
log "Active Python in venv: ${ACTIVE_PYTHON_VERSION}"

# Upgrade pip
log "Upgrading pip"
pip install --upgrade pip --quiet

# ==========================================
# REPOSITORY MANAGEMENT
# ==========================================
log "Managing Git repository"

# Prepare Git URL with token if provided
if [ ! -z "${GIT_TOKEN}" ]; then
    # Extract repo path and inject token
    REPO_PATH=$(echo ${GIT_REPO_URL} | sed 's|https://github.com/||')
    GIT_URL_WITH_AUTH="https://${GIT_TOKEN}@github.com/${REPO_PATH}"
else
    GIT_URL_WITH_AUTH="${GIT_REPO_URL}"
fi

if [ -d "${REPO_DIR}" ]; then
    log "Repository exists. Pulling latest changes"
    cd ${REPO_DIR}
    
    # Fetch and checkout
    git fetch origin || error_exit "Failed to fetch from remote"
    git checkout ${GIT_BRANCH} || error_exit "Failed to checkout branch ${GIT_BRANCH}"
    git pull origin ${GIT_BRANCH} || error_exit "Failed to pull latest changes"
    
    CURRENT_COMMIT=$(git rev-parse HEAD)
    log "Current commit: ${CURRENT_COMMIT}"
else
    log "Cloning repository"
    mkdir -p $(dirname ${REPO_DIR})
    
    git clone -b ${GIT_BRANCH} ${GIT_URL_WITH_AUTH} ${REPO_DIR} || error_exit "Failed to clone repository"
    
    cd ${REPO_DIR}
    CURRENT_COMMIT=$(git rev-parse HEAD)
    log "Repository cloned. Commit: ${CURRENT_COMMIT}"
fi

# ==========================================
# DEPENDENCY INSTALLATION
# ==========================================
log "Installing Python dependencies"

# Check for requirements file
if [ -f "${REQUIREMENTS_FILE}" ]; then
    log "Found ${REQUIREMENTS_FILE}. Installing dependencies..."
    pip install -r ${REQUIREMENTS_FILE} || error_exit "Failed to install requirements"
    log "Dependencies installed successfully"
else
    warning "${REQUIREMENTS_FILE} not found. Skipping dependency installation"
fi

# Install additional packages if specified
if [ ! -z "${ADDITIONAL_PACKAGES}" ]; then
    log "Installing additional packages: ${ADDITIONAL_PACKAGES}"
    pip install ${ADDITIONAL_PACKAGES} || error_exit "Failed to install additional packages"
fi

# ==========================================
# SCRIPT EXECUTION
# ==========================================
log "=========================================="
log "Executing Python Script"
log "=========================================="
log "Script: ${SCRIPT_PATH}"
log "Arguments: ${SCRIPT_ARGS}"

# Check if script exists
if [ ! -f "${SCRIPT_PATH}" ]; then
    error_exit "Script not found: ${SCRIPT_PATH}"
fi

# Execute the script
START_TIME=$(date +%s)
log "Execution started at: $(date)"

# Run script and capture exit code
python ${SCRIPT_PATH} ${SCRIPT_ARGS}
EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

log "Execution completed at: $(date)"
log "Duration: ${DURATION} seconds"
log "Exit code: ${EXIT_CODE}"

# ==========================================
# CLEANUP AND EXIT
# ==========================================
deactivate

if [ ${EXIT_CODE} -eq 0 ]; then
    log "=========================================="
    log "Job completed successfully"
    log "=========================================="
    exit 0
else
    error_exit "Job failed with exit code ${EXIT_CODE}"
fi
