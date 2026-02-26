import requests
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Union
import click

class APIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.token = self._load_token()
    
    def _load_token(self):
        """Load token from file if exists"""
        token_file = Path.home() / ".auction-cli" / "token"
        if token_file.exists():
            return token_file.read_text().strip()
        return None
    
    def _save_token(self, token):
        """Save token to file with secure permissions"""
        token_file = Path.home() / ".auction-cli" / "token"
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token)
        token_file.chmod(0o600)  # Owner read/write only
        self.token = token
    
    def _delete_token(self):
        """Delete token file"""
        token_file = Path.home() / ".auction-cli" / "token"
        if token_file.exists():
            token_file.unlink()
        self.token = None
        
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Any:
        """Make HTTP request to API"""
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        if data:
            headers["Content-Type"] = "application/json"
        else:
            data = None
            
        # Make HTTP request
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            if data:
                response = requests.post(url, headers=headers, json=data)
            else:
                response = requests.post(url, headers=headers)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Handle HTTP errors
        if response.status_code >= 400:
            self._handle_error_response(response)
            return None
            
        return response.json()
    
    def _handle_error_response(self, response):
        """Handle HTTP error responses"""
        if response.status_code == 401:
            click.echo("Error: Authentication failed. Please login again.")
            self._delete_token()
        elif response.status_code == 403:
            click.echo("Error: You don't have permission to perform this action.")
        elif response.status_code == 404:
            click.echo("Error: Resource not found.")
        elif response.status_code >= 400:
            try:
                error_data = response.json()
                click.echo(f"Error: {error_data.get('detail', 'Unknown error')}")
            except:
                click.echo(f"Error: HTTP {response.status_code}")
        else:
            click.echo(f"Error: HTTP {response.status_code}")
    
    def _handle_http_error(self, response):
        """Handle HTTP error responses"""
        if response.status_code == 401:
            click.echo("Error: Authentication failed. Please login again.")
            self._delete_token()
        elif response.status_code == 403:
            click.echo("Error: You don't have permission to perform this action.")
        elif response.status_code == 404:
            click.echo("Error: Resource not found.")
        elif response.status_code >= 400:
            try:
                error_data = response.json()
                click.echo(f"Error: {error_data.get('detail', 'Unknown error')}")
            except:
                click.echo(f"Error: HTTP {response.status_code}")
        else:
            click.echo(f"Error: HTTP {response.status_code}")
    
    # Authentication methods
    def register(self, name: str, email: str, password: str, role: str) -> Dict:
        """Register new user"""
        data = {"name": name, "email": email, "password": password, "role": role}
        return self._make_request("POST", "/auth/register", data)
    
    def login(self, email: str, password: str) -> bool:
        """Login user and store token"""
        from urllib.parse import urlencode
        
        # Use form data as expected by OAuth2PasswordRequestForm
        data = {"username": email, "password": password}
        url = f"{self.base_url}/auth/login"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        response = requests.post(url, headers=headers, data=urlencode(data))
        
        if response.status_code >= 400:
            self._handle_http_error(response)
            return False
        
        response_data = response.json()
        if "access_token" in response_data:
            self._save_token(response_data["access_token"])
            return True
        
        return False
    
    def logout(self):
        """Logout and clear stored token"""
        self._delete_token()
        return True
    
    def get_current_user(self):
        """Get current user info"""
        if not self.token:
            return None
        return self._make_request("GET", "/auth/me")
    
    # Auction methods
    def get_auctions(self) -> List:
        """Get all auctions"""
        result = self._make_request("GET", "/auctions/get_auctions")
        return result if isinstance(result, list) else []
    
    def get_auction(self, auction_id: int) -> Dict:
        """Get specific auction"""
        result = self._make_request("GET", f"/auctions/{auction_id}")
        return result if isinstance(result, dict) else {}
    
    def create_auction(self, name: str, ended_at: Union[str, None] = None) -> Dict:
        """Create new auction. ended_at must be ISO datetime string if provided."""
        data: Dict[str, Any] = {"name": name}
        if ended_at is not None:
            data["ended_at"] = ended_at
        result = self._make_request("POST", "/auctions/", data)
        return result if isinstance(result, dict) else {}
    
    def end_auction(self, auction_id: int) -> Dict:
        """End auction"""
        result = self._make_request("POST", f"/managers/auctions/{auction_id}/end")
        return result if isinstance(result, dict) else {}
    
    # Item methods
    def add_item(self, auction_id: int, name: str, opening_price: float) -> Dict:
        """Add item to auction"""
        data = {"name": name, "opening_price": opening_price, "auction_id": auction_id}
        result = self._make_request("POST", f"/managers/auctions/{auction_id}/items", data)
        return result if isinstance(result, dict) else {}
    
    # Bid methods
    def place_bid(self, item_id: int, amount: float) -> Dict:
        """Place bid on item"""
        data = {"item_id": item_id, "amount": amount}
        result = self._make_request("POST", "/customers/bid", data)
        return result if isinstance(result, dict) else {}
    
    def get_user_bids(self) -> List:
        """Get current user's bids"""
        result = self._make_request("GET", "/customers/bids")
        return result if isinstance(result, list) else []