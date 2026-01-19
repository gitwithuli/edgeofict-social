"""Cloudinary image upload client."""
import os
import base64
import hashlib
import time
import requests


class CloudinaryClient:
    """Client for uploading images to Cloudinary."""

    def __init__(self):
        self.cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
        self.api_key = os.getenv('CLOUDINARY_API_KEY')
        self.api_secret = os.getenv('CLOUDINARY_API_SECRET')
        self.upload_url = f'https://api.cloudinary.com/v1_1/{self.cloud_name}/image/upload'

    def is_configured(self):
        """Check if Cloudinary credentials are configured."""
        return bool(self.cloud_name and self.api_key and self.api_secret)

    def _generate_signature(self, params):
        """Generate signature for authenticated upload."""
        sorted_params = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
        to_sign = sorted_params + self.api_secret
        return hashlib.sha1(to_sign.encode()).hexdigest()

    def upload_base64(self, base64_data, folder='edgeofict', public_id=None):
        """Upload a base64 encoded image to Cloudinary.

        Args:
            base64_data: Base64 string (with or without data URI prefix)
            folder: Folder name in Cloudinary
            public_id: Optional custom public ID for the image

        Returns:
            dict with secure_url and public_id
        """
        if not self.is_configured():
            raise ValueError("Cloudinary credentials not configured")

        # Ensure proper data URI format
        if not base64_data.startswith('data:'):
            base64_data = f'data:image/png;base64,{base64_data}'

        timestamp = int(time.time())

        params = {
            'timestamp': timestamp,
            'folder': folder,
        }

        if public_id:
            params['public_id'] = public_id

        signature = self._generate_signature(params)

        payload = {
            'file': base64_data,
            'api_key': self.api_key,
            'signature': signature,
            **params
        }

        response = requests.post(self.upload_url, data=payload)
        data = response.json()

        if 'error' in data:
            raise Exception(data['error'].get('message', 'Upload failed'))

        return {
            'success': True,
            'secure_url': data.get('secure_url'),
            'public_id': data.get('public_id'),
            'url': data.get('url')
        }

    def verify_credentials(self):
        """Verify Cloudinary credentials are valid."""
        if not self.is_configured():
            return {'configured': False, 'error': 'Credentials not set'}

        # Try to ping the API
        try:
            url = f'https://api.cloudinary.com/v1_1/{self.cloud_name}/resources/image'
            response = requests.get(url, auth=(self.api_key, self.api_secret))
            if response.status_code == 200:
                return {
                    'configured': True,
                    'status': 'ok',
                    'cloud_name': self.cloud_name
                }
            else:
                return {'configured': False, 'error': 'Invalid credentials'}
        except Exception as e:
            return {'configured': False, 'error': str(e)}
