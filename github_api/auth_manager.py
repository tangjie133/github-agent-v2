"""
GitHub App Authentication Manager
Handles JWT generation and Installation Token retrieval
"""

import os
import time
import jwt
import requests
from typing import Optional, Dict, Any
from pathlib import Path


class GitHubAuthManager:
    """Manages GitHub App authentication"""
    
    def __init__(self, app_id: str = None, private_key_path: str = None):
        self.app_id = app_id or os.environ.get("GITHUB_APP_ID")
        self.private_key_path = private_key_path or os.environ.get(
            "GITHUB_APP_PRIVATE_KEY_PATH"
        )
        self._private_key = None
        self._installation_tokens: Dict[str, tuple] = {}  # {installation_id: (token, expiry)}
        
    def _load_private_key(self) -> str:
        """Load private key from file"""
        if self._private_key is None:
            if not self.private_key_path:
                raise ValueError("GITHUB_APP_PRIVATE_KEY_PATH not set")
            
            key_path = Path(self.private_key_path)
            if not key_path.exists():
                raise FileNotFoundError(f"Private key not found: {self.private_key_path}")
            
            with open(key_path, 'r') as f:
                self._private_key = f.read()
        
        return self._private_key
    
    def _generate_jwt(self) -> str:
        """Generate JWT for GitHub App authentication"""
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued at (60 seconds ago to avoid clock skew)
            "exp": now + 600,  # Expires in 10 minutes
            "iss": self.app_id
        }
        
        private_key = self._load_private_key()
        return jwt.encode(payload, private_key, algorithm="RS256")
    
    def get_installation_token(self, installation_id: str) -> str:
        """
        Get installation access token (cached for 1 hour)
        
        Args:
            installation_id: GitHub App installation ID
            
        Returns:
            Installation access token
        """
        # Check cache
        if installation_id in self._installation_tokens:
            token, expiry = self._installation_tokens[installation_id]
            if time.time() < expiry - 300:  # Refresh 5 minutes before expiry
                return token
        
        # Get new token
        jwt_token = self._generate_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        token = data["token"]
        expiry = time.time() + 3600  # 1 hour
        
        self._installation_tokens[installation_id] = (token, expiry)
        return token
