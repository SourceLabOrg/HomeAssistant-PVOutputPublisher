# Developer Guide

Welcome to the development guide for **HomeAssistant-PVOutputPublisher**. This document outlines how to set up your local development environment, run tests, and prepare/publish releases.

---

## 1. Development Environment Setup

### Prerequisites
* **Python 3.13+** (matching current Home Assistant core requirements)
* `git`
* Optional: [`uv`](https://github.com/astral-sh/uv) (for ultra-fast environment setup)

### Setup Steps

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/SourceLabOrg/HomeAssistant-PVOutputPublisher.git
   cd HomeAssistant-PVOutputPublisher
   ```

2. **Create and Activate a Virtual Environment:**
   * Using standard `venv`:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * Or using `uv`:
     ```bash
     uv venv
     source .venv/bin/activate
     ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements_test.txt
   ```
   *(Or `uv pip install -r requirements_test.txt`)*

---

## 2. Running Tests & Code Quality

The integration uses [`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) for testing with Home Assistant's mock fixtures.

### Run Test Suite
```bash
pytest
```

### Run with Coverage Report
```bash
pytest --cov=custom_components/pvoutput_publisher --cov-report=term-missing
```

---

## 3. Local Testing Against Home Assistant

Since Home Assistant custom components are pure Python packages, there is **no build step**.

1. Copy the [`custom_components/pvoutput_publisher/`](../custom_components/pvoutput_publisher) folder into your Home Assistant installation:
   ```
   /config/custom_components/pvoutput_publisher/
   ```
   * *Via SCP:*
     ```bash
     scp -r custom_components/pvoutput_publisher root@<YOUR_HA_IP>:/config/custom_components/
     ```
   * *Via Samba / Studio Code Server:* Drag and drop the folder into `/config/custom_components/`.

2. **Restart Home Assistant:**
   Navigate to **Settings > System > Restart** (and hard-refresh your browser with `Cmd+Shift+R` / `Ctrl+Shift+R` if translation files changed).

3. Check logs in **Settings > System > Logs** to verify initialization, migration, and periodic upload payloads.

---

## 4. Release Process

To create a new release for users (via HACS and GitHub):

### Step 1: Version Bumping
1. Update `"version"` in [`custom_components/pvoutput_publisher/manifest.json`](../custom_components/pvoutput_publisher/manifest.json):
   ```json
   {
     "version": "X.Y.Z"
   }
   ```
2. Update [`CHANGELOG.md`](../CHANGELOG.md):
   * Add a new section `## X.Y.Z (MM/DD/YYYY)`.
   * Document Breaking Changes, Feature Changes, Bug Fixes, and any specific Migration Notes.

### Step 2: Verification
1. Run all unit tests to ensure 100% pass rate:
   ```bash
   pytest
   ```
2. Verify all translation files in [`translations/`](../custom_components/pvoutput_publisher/translations) match any schema changes made in `config_flow.py` (and use `description_placeholders` rather than hardcoded URLs so `hassfest` passes).

### Step 3: Git Commit & Tag
1. Commit all changes:
   ```bash
   git add .
   git commit -m "Release X.Y.Z"
   ```
2. Push branch and merge to `main`.

### Step 4: Publish GitHub Release (HACS Changelog)
HACS pulls release changelogs directly from **GitHub Releases**:
1. On GitHub, navigate to **Releases > Draft a new release** (or use `gh release create vX.Y.Z`).
2. Tag version: `vX.Y.Z` (e.g. `v2.1.0`).
3. Title: `Release vX.Y.Z` (or `vX.Y.Z`).
4. **Description:** Copy and paste the exact markdown section from `CHANGELOG.md` for this version into the GitHub release description.
5. Click **Publish Release**.
6. Publishing the release automatically triggers [`.github/workflows/release.yaml`](../.github/workflows/release.yaml), which builds `pvoutput_publisher.zip` from `custom_components/pvoutput_publisher` and attaches it to the release so HACS can track download counts.
7. HACS will automatically detect the new release and display the release notes inside Home Assistant for updating users.
