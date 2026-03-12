"""
GitHub API Client
Wraps GitHub REST API calls with authentication
"""

import base64
import requests
from typing import Optional, Dict, Any, List
from .auth_manager import GitHubAuthManager


class GitHubClient:
    """GitHub API client for repository operations"""
    
    def __init__(self, auth_manager: GitHubAuthManager, installation_id: str = None):
        self.auth = auth_manager
        self.installation_id = installation_id
        self.base_url = "https://api.github.com"
    
    def with_installation(self, installation_id: str) -> 'GitHubClient':
        """Create a new client with specific installation ID"""
        return GitHubClient(self.auth, installation_id)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated request headers"""
        token = self.auth.get_installation_token(self.installation_id)
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information"""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get issue details"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_issue_comments(self, owner: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
        """Get all comments for an issue"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        """Create a comment on an issue"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        data = {"body": body}
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()
    
    def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> Optional[str]:
        """Get file content from repository"""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        headers = self._get_headers()
        params = {"ref": ref}
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        
        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        return data.get("content")
    
    def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create or update a file in the repository"""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        
        data = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "branch": branch
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()
    
    def create_branch(self, owner: str, repo: str, branch: str, from_branch: str = "main") -> Dict[str, Any]:
        """Create a new branch"""
        # Get base branch SHA
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{from_branch}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        base_sha = response.json()["object"]["sha"]
        
        # Create new branch
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs"
        data = {
            "ref": f"refs/heads/{branch}",
            "sha": base_sha
        }
        response = requests.post(url, headers=self._get_headers(), json=data)
        
        # If branch already exists, return existing
        if response.status_code == 422:
            url = f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
        else:
            response.raise_for_status()
        
        return response.json()
    
    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        issue_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a pull request"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        
        # Link to issue if provided
        if issue_number:
            body = f"Closes #{issue_number}\n\n{body}"
        
        data = {
            "title": title,
            "head": head,
            "base": base,
            "body": body
        }
        
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()
    
    def get_clone_url(self, owner: str, repo: str) -> str:
        """Get authenticated clone URL"""
        token = self.auth.get_installation_token(self.installation_id)
        return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
