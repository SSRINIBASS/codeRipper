#!/usr/bin/env python3
"""
Pipeline Verification Script for Repo Intelligence Platform.

This script tests the end-to-end pipeline by:
1. Checking API health
2. Triggering repository ingestion
3. Polling for status until processing is complete
4. Verifying repository structure
5. Testing the tutor with a sample question
"""

import argparse
import sys
import time

import requests

# --- Configuration ---
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_REPO_URL = "https://github.com/octocat/Hello-World"
POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 60  # 5 minutes max wait


def check_health(base_url: str) -> bool:
    """Check if the API is healthy."""
    print("\n--- Step 1: Checking API Health ---")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print(f"  ✅ API is healthy: {response.json()}")
            return True
        else:
            print(f"  ❌ API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Could not connect to API at {base_url}")
        return False


def trigger_ingestion(base_url: str, repo_url: str, force: bool = False) -> dict | None:
    """Trigger repository ingestion."""
    print(f"\n--- Step 2: Triggering Ingestion for {repo_url} ---")
    try:
        response = requests.post(
            f"{base_url}/repos/ingest",
            json={"repo_url": repo_url, "force": force},
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Ingestion started: repo_id={data['repo_id']}, job_id={data['job_id']}")
            return data
        else:
            print(f"  ❌ Ingestion failed with status {response.status_code}: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return None


def poll_status(base_url: str, repo_id: str) -> str | None:
    """Poll repository status until it reaches a terminal state."""
    print(f"\n--- Step 3: Polling Status for repo_id={repo_id} ---")
    terminal_states = {"INDEXED", "DOCS_GENERATED", "READY", "FAILED"}
    indexing_triggered = False
    
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        try:
            response = requests.get(f"{base_url}/repos/{repo_id}/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                print(f"  [{attempt}/{MAX_POLL_ATTEMPTS}] Status: {status}")
                
                # If we reach STRUCTURED, trigger indexing
                if status == "STRUCTURED" and not indexing_triggered:
                    print("  ➡️  Triggering indexing...")
                    try:
                        index_response = requests.post(
                            f"{base_url}/intelligence/{repo_id}/index",
                            json={},
                            timeout=30,
                        )
                        if index_response.status_code == 200:
                            index_data = index_response.json()
                            print(f"  ✅ Indexing started: job_id={index_data.get('job_id')}")
                            indexing_triggered = True
                        else:
                            print(f"  ⚠️  Indexing request returned {index_response.status_code}: {index_response.text}")
                    except requests.exceptions.RequestException as e:
                        print(f"  ⚠️  Failed to trigger indexing: {e}")
                
                if status in terminal_states:
                    if status == "FAILED":
                        print(f"  ❌ Processing failed: {data.get('error_message')}")
                        return None
                    print(f"  ✅ Reached terminal state: {status}")
                    return status
            else:
                print(f"  ⚠️  Status check returned {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Request failed: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)
    
    print(f"  ❌ Timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS} seconds")
    return None


def verify_structure(base_url: str, repo_id: str) -> bool:
    """Verify repository structure is available."""
    print("\n--- Step 4: Verifying Repository Structure ---")
    try:
        response = requests.get(f"{base_url}/repos/{repo_id}/structure", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Structure retrieved: {data.get('total_files', 0)} files, {data.get('total_directories', 0)} directories")
            return True
        else:
            print(f"  ❌ Failed to get structure: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return False


def test_tutor(base_url: str, repo_id: str) -> bool:
    """Test the tutor with a sample question."""
    print("\n--- Step 5: Testing Tutor ---")
    
    # First, create a session
    print("  Creating tutor session...")
    try:
        session_response = requests.post(
            f"{base_url}/tutor/{repo_id}/session",
            json={},
            timeout=30,
        )
        if session_response.status_code != 200:
            print(f"  ❌ Failed to create session: {session_response.status_code} - {session_response.text}")
            return False
        
        session_data = session_response.json()
        session_id = session_data.get("session_id")
        print(f"  ✅ Session created: {session_id}")
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return False
    
    # Now ask a question
    print("  Asking a question...")
    question = "What is this repository about?"
    try:
        ask_response = requests.post(
            f"{base_url}/tutor/{repo_id}/ask",
            json={"session_id": session_id, "question": question},
            timeout=60,
        )
        if ask_response.status_code == 200:
            answer_data = ask_response.json()
            answer = answer_data.get("answer", "")
            print(f"  ✅ Received answer ({len(answer)} chars):")
            print(f"     \"{answer[:200]}{'...' if len(answer) > 200 else ''}\"")
            return True
        else:
            print(f"  ❌ Ask failed: {ask_response.status_code} - {ask_response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Verify the Repo Intelligence Pipeline")
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help=f"GitHub repository URL to test (default: {DEFAULT_REPO_URL})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingestion even if repository exists",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()
    
    base_url = args.base_url
    
    print("=" * 60)
    print("  Repo Intelligence Platform - Pipeline Verification")
    print("=" * 60)
    
    # Step 1: Health check
    if not check_health(base_url):
        print("\n❌ VERIFICATION FAILED: API is not healthy")
        sys.exit(1)
    
    # Step 2: Trigger ingestion
    ingest_result = trigger_ingestion(base_url, args.repo_url, force=args.force)
    if not ingest_result:
        print("\n❌ VERIFICATION FAILED: Could not start ingestion")
        sys.exit(1)
    
    repo_id = ingest_result["repo_id"]
    
    # Step 3: Poll status
    final_status = poll_status(base_url, repo_id)
    if not final_status:
        print("\n❌ VERIFICATION FAILED: Processing did not complete successfully")
        sys.exit(1)
    
    # Step 4: Verify structure
    if not verify_structure(base_url, repo_id):
        print("\n❌ VERIFICATION FAILED: Could not verify repository structure")
        sys.exit(1)
    
    # Step 5: Test tutor (only if INDEXED or higher)
    if final_status in {"INDEXED", "DOCS_GENERATED", "READY"}:
        if not test_tutor(base_url, repo_id):
            print("\n⚠️  WARNING: Tutor test failed, but pipeline is mostly working")
    else:
        print("\n  ⏭️  Skipping tutor test (status is not INDEXED or higher)")
    
    print("\n" + "=" * 60)
    print("  ✅ PIPELINE VERIFICATION COMPLETE")
    print("=" * 60)
    print(f"\n  Repository ID: {repo_id}")
    print(f"  Final Status:  {final_status}")
    print("\nYou can now interact with the repository via the API.")


if __name__ == "__main__":
    main()
