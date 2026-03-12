"""
GitHub Webhook Server for Agent V2
Receives GitHub webhooks and routes to appropriate handlers
"""

import os
import json
import hmac
import hashlib
import logging
from flask import Flask, request, jsonify
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import GitHubEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
WEBHOOK_DIR = os.environ.get("GITHUB_AGENT_WEBHOOK_DIR", "/tmp/github-webhooks-v2")


class WebhookServer:
    """GitHub Webhook server"""
    
    def __init__(self, processor=None):
        self.processor = processor
        self.webhook_dir = Path(WEBHOOK_DIR)
        self.webhook_dir.mkdir(parents=True, exist_ok=True)
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        if not WEBHOOK_SECRET:
            return True  # Skip verification if secret not set
        
        if not signature:
            return False
        
        expected_signature = "sha256=" + hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def save_webhook(self, event_type: str, data: Dict[str, Any]) -> Path:
        """Save webhook to file for debugging/audit"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        repo_name = data.get("repository", {}).get("name", "unknown")
        
        if "issue" in data:
            issue_number = data["issue"].get("number", 0)
            filename = f"{event_type}-{repo_name}-{issue_number}-{timestamp}.json"
        else:
            filename = f"{event_type}-{repo_name}-{timestamp}.json"
        
        filepath = self.webhook_dir / filename
        
        # Add metadata
        data["event_type"] = event_type
        data["received_at"] = datetime.now().isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved webhook to: {filepath}")
        return filepath
    
    def parse_event(self, payload: Dict[str, Any], event_type: str) -> Optional[GitHubEvent]:
        """Parse webhook payload into GitHubEvent"""
        try:
            return GitHubEvent(
                event_type=event_type,
                action=payload.get("action", ""),
                repository=payload.get("repository", {}),
                issue=payload.get("issue"),
                comment=payload.get("comment"),
                installation=payload.get("installation"),
                sender=payload.get("sender")
            )
        except Exception as e:
            logger.error(f"Failed to parse event: {e}")
            return None
    
    def handle_webhook(self) -> tuple:
        """Main webhook handler"""
        # Get headers
        signature = request.headers.get("X-Hub-Signature-256", "")
        event_type = request.headers.get("X-GitHub-Event", "unknown")
        
        # Get payload
        payload = request.get_data()
        
        # Verify signature
        if not self.verify_signature(payload, signature):
            logger.warning("Invalid webhook signature")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse JSON
        try:
            data = request.get_json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Log event
        logger.info(f"Received {event_type} event")
        
        # Save webhook
        try:
            self.save_webhook(event_type, data)
        except Exception as e:
            logger.error(f"Failed to save webhook: {e}")
        
        # Process event
        if event_type in ["issues", "issue_comment"]:
            event = self.parse_event(data, event_type)
            if event and self.processor:
                # Async processing
                import threading
                thread = threading.Thread(
                    target=self.processor.process_event,
                    args=(event,),
                    daemon=True
                )
                thread.start()
                logger.info(f"Started async processing for {event_type}")
        else:
            logger.info(f"Ignored event type: {event_type}")
        
        return jsonify({
            "status": "ok",
            "event": event_type,
            "message": "Webhook received and processing"
        }), 200


# Flask routes
webhook_server = WebhookServer()

@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    """GitHub webhook endpoint"""
    return webhook_server.handle_webhook()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "version": "2.0.0",
        "webhook_dir": str(webhook_server.webhook_dir),
        "secret_configured": bool(WEBHOOK_SECRET)
    })


@app.route("/webhooks", methods=["GET"])
def list_webhooks():
    """List saved webhook files"""
    webhooks = []
    for f in sorted(webhook_server.webhook_dir.glob("*.json")):
        stat = f.stat()
        webhooks.append({
            "filename": f.name,
            "path": str(f),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    return jsonify({"webhooks": webhooks})


def run_server(host: str = "0.0.0.0", port: int = 8080, processor=None):
    """Run the webhook server"""
    global webhook_server
    webhook_server.processor = processor
    
    logger.info(f"Starting webhook server on {host}:{port}")
    logger.info(f"Webhook directory: {webhook_server.webhook_dir}")
    logger.info(f"Secret configured: {bool(WEBHOOK_SECRET)}")
    
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Agent V2 Webhook Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port)
