import msal
import os
import time
import logging
import requests
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AzureConnection:
    """Handle Azure AD authentication and token management."""

    def __init__(self, tenant_id: str, app_client_id: str):
        """
        Initialize Azure connection.
        Args:
            tenant_id: Azure AD tenant ID
            app_client_id: Application client ID for scope
        """
        self.tenant_id = tenant_id
        self.app_client_id = app_client_id
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.scope = [f"api://{app_client_id}/.default"]

        # Token caching
        self._cached_token = None
        self._token_expires_at = None

        logger.info(f"🔧 Azure connection initialized for tenant: {tenant_id}")

    def get_access_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """
        Acquire access token from Azure AD using client credentials flow.
        Args:
            client_id: Azure AD client ID
            client_secret: Azure AD client secret
        Returns:
            Access token string or None if acquisition fails
        """
        # Check if we have a valid cached token
        if self._is_token_valid():
            logger.debug("🔑 Using cached Azure token")
            return self._cached_token

        try:
            logger.debug("🔑 Acquiring new Azure token...")
            app = msal.ConfidentialClientApplication(
                client_id,
                authority=self.authority,
                client_credential=client_secret
            )
            result = app.acquire_token_for_client(scopes=self.scope)

            if "access_token" in result:
                self._cached_token = result["access_token"]
                # Set expiration time (default to 1 hour if not provided)
                expires_in = result.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in - 300  # 5 min buffer

                logger.info("✅ Azure token acquired successfully")
                return self._cached_token
            else:
                logger.error(f"❌ Error acquiring token: {result.get('error')}")
                logger.error(f"   Error description: {result.get('error_description')}")
                return None

        except Exception as e:
            logger.error(f"❌ Exception while acquiring token: {e}")
            return None

    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid"""
        if not self._cached_token or not self._token_expires_at:
            return False
        return time.time() < self._token_expires_at

    def validate_token(self, token: str) -> bool:
        """
        Basic validation to check if token exists and is not empty.
        Args:
            token: Access token to validate
        Returns:
            True if token appears valid, False otherwise
        """
        return token is not None and len(token) > 0

    def clear_token_cache(self):
        """Clear cached token to force refresh"""
        self._cached_token = None
        self._token_expires_at = None
        logger.debug("🧹 Azure token cache cleared")


class PrecheckAPI:
    """Handle API requests to the precheck service with retry logic."""

    def __init__(self, max_retries: int = 5, retry_delay: int = 10, webhook_config: Optional[Dict] = None):
        """
        Initialize API handler.
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay in seconds between retries
            webhook_config: Webhook configuration dictionary
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.webhook_config = webhook_config or {}

    def _make_request_with_retry(self, method: str, token: str, api_url: str, data: Optional[dict] = None) -> dict:
        """Make HTTP request with retry logic."""
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }

        if data:
            headers["Content-Type"] = "application/json"

        for attempt in range(1, self.max_retries + 1):
            try:
                if method.upper() == 'GET':
                    response = requests.get(api_url, headers=headers, timeout=30)
                elif method.upper() == 'POST':
                    response = requests.post(api_url, headers=headers, json=data, timeout=30)
                else:
                    return {"error": f"Unsupported HTTP method: {method}"}

                response.raise_for_status()
                logger.info(f"✅ Success on attempt {attempt}")
                return response.json()

            except requests.exceptions.RequestException as e:
                error_info = {
                    "error": str(e),
                    "status_code": getattr(e.response, 'status_code', None),
                    "attempt": attempt
                }

                if attempt < self.max_retries:
                    logger.warning(f"⚠️ Attempt {attempt} failed: {e}")
                    logger.info(f"🔄 Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ All {self.max_retries} attempts failed")
                    return error_info

        return {"error": "Max retries exceeded"}

    def get(self, token: str, api_url: str) -> dict:
        """Make GET request to the API."""
        logger.info(f"🔍 Making GET request to: {api_url}")
        return self._make_request_with_retry('GET', token, api_url)

    def post(self, token: str, api_url: str, data: dict) -> dict:
        """Make POST request to the API."""
        logger.info(f"📤 Making POST request to: {api_url}")
        return self._make_request_with_retry('POST', token, api_url, data)

    def send_webhook_notification(self, failure_info: dict) -> None:
        """Send webhook notification when requests fail."""
        if not self.webhook_config.get('enabled', False):
            return

        webhook_url = self.webhook_config.get('url')
        if not webhook_url:
            logger.warning("⚠️ Webhook URL not configured")
            return

        payload = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": "API Request Failure",
            "environment": failure_info.get('environment'),
            "api_url": failure_info.get('api_url'),
            "error": failure_info.get('error'),
            "attempts": failure_info.get('attempt', self.max_retries),
            "status_code": failure_info.get('status_code')
        }

        try:
            logger.info(f"📢 Sending webhook notification to {webhook_url}...")
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("✅ Webhook notification sent successfully")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send webhook notification: {e}")


class PrecheckServiceMonitor:
    """Enhanced precheck service monitor integrated with Universal Neural System."""

    def __init__(self, config_path: str = None):
        """Initialize monitor with configuration."""
        # Try to find config file in multiple locations
        config_locations = [
            config_path,
            "precheck/precheck_service_monitor/config.json",
            "config/precheck_monitor_config.json",
            os.path.join(os.path.dirname(__file__), "../precheck/precheck_service_monitor/config.json")
        ]

        self.config = None
        for location in config_locations:
            if location and os.path.exists(location):
                self.config = self._load_config(location)
                logger.info(f"✅ Loaded precheck monitor config from: {location}")
                break

        if not self.config:
            logger.warning("⚠️ No precheck monitor config found, using defaults")
            self.config = self._get_default_config()

        # Initialize API handler
        retry_config = self.config.get('retry_config', {})
        webhook_config = self.config.get('webhook', {})

        self.api = PrecheckAPI(
            max_retries=retry_config.get('max_retries', 5),
            retry_delay=retry_config.get('retry_delay_seconds', 10),
            webhook_config=webhook_config
        )

        # Cache for service health
        self._service_cache = {}
        self._cache_expiry = {}

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing JSON configuration: {e}")

    def _get_default_config(self) -> dict:
        """Get default configuration when no config file is found."""
        return {
            "retry_config": {
                "max_retries": 5,
                "retry_delay_seconds": 10
            },
            "webhook": {
                "url": os.getenv('PRECHECK_WEBHOOK_URL', ''),
                "enabled": os.getenv('PRECHECK_WEBHOOK_ENABLED', 'false').lower() == 'true'
            },
            "environments": []
        }

    def get_service_health(self) -> Dict[str, Any]:
        """Get comprehensive service health from all configured environments."""
        # Check cache first
        cache_key = 'all_environments_health'
        if self._is_cache_valid(cache_key):
            logger.debug("📊 Using cached precheck service health data")
            return self._service_cache[cache_key]

        environments = self.config.get('environments', [])
        if not environments:
            return {
                'status': 'no_config',
                'services': {},
                'message': 'No environments configured for monitoring',
                'timestamp': time.time()
            }

        all_services = {}
        overall_status = 'healthy'
        failed_services = 0
        total_services = 0

        for env_config in environments:
            env_results = self._monitor_environment_health(env_config)
            env_name = env_config.get('name', 'unknown')

            for api_config in env_config.get('api_urls', []):
                service_key = f"{env_name}_{api_config['name']}"
                total_services += 1

                # Find result for this API
                api_result = next(
                    (r for r in env_results if r.get('api_name') == api_config['name']),
                    None
                )

                if api_result and 'error' not in api_result.get('response', {}):
                    all_services[service_key] = {
                        'status': 'running',
                        'health': 'good',
                        'environment': env_name,
                        'api_name': api_config['name'],
                        'api_url': api_config['url'],
                        'last_checked': time.time()
                    }
                else:
                    failed_services += 1
                    error_msg = 'Unknown error'
                    if api_result:
                        error_msg = api_result.get('response', {}).get('error', error_msg)

                    all_services[service_key] = {
                        'status': 'failed',
                        'health': 'poor',
                        'environment': env_name,
                        'api_name': api_config['name'],
                        'api_url': api_config['url'],
                        'error': error_msg,
                        'last_checked': time.time()
                    }

        # Determine overall status
        if failed_services == 0:
            overall_status = 'healthy'
        elif failed_services < total_services / 2:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'

        health_data = {
            'status': overall_status,
            'services': all_services,
            'total_services': total_services,
            'failed_services': failed_services,
            'success_rate': (total_services - failed_services) / max(1, total_services),
            'message': f'Precheck service monitoring: {total_services} services, {failed_services} failed',
            'timestamp': time.time()
        }

        # Cache the result
        self._service_cache[cache_key] = health_data
        self._cache_expiry[cache_key] = time.time() + 300  # 5 minutes

        return health_data

    def _monitor_environment_health(self, env_config: dict) -> List[dict]:
        """Monitor a specific environment and return results."""
        env_name = env_config['name']
        tenant_id = env_config['tenant_id']
        openapi_client_id = env_config['openapi_client_id']
        app_client_id = env_config['app_client_id']
        client_secret_env = env_config['client_secret_env']
        api_urls = env_config.get('api_urls', [])

        # Get client secret from environment variable
        client_secret = os.getenv(client_secret_env)
        if not client_secret:
            error_msg = f"{client_secret_env} environment variable not set"
            logger.error(f"❌ {error_msg}")
            return [{"environment": env_name, "error": error_msg}]

        # Initialize Azure connection
        azure_conn = AzureConnection(tenant_id, app_client_id)
        token = azure_conn.get_access_token(app_client_id, client_secret)

        if not token:
            error_msg = "Failed to acquire access token"
            logger.error(f"❌ {error_msg}")
            return [{"environment": env_name, "error": error_msg}]

        # Test all API endpoints
        results = []
        for api_config in api_urls:
            api_name = api_config['name']
            api_url = api_config['url']

            logger.debug(f"🔍 Testing {env_name}/{api_name}: {api_url}")
            response = self.api.get(token, api_url)

            result = {
                "environment": env_name,
                "api_name": api_name,
                "api_url": api_url,
                "response": response
            }

            if "error" in response:
                logger.warning(f"❌ {env_name}/{api_name} failed: {response['error']}")
                # Send webhook notification
                failure_info = {
                    "environment": env_name,
                    "api_name": api_name,
                    "api_url": api_url,
                    "error": response['error'],
                    "status_code": response.get('status_code'),
                    "attempt": response.get('attempt')
                }
                self.api.send_webhook_notification(failure_info)
            else:
                logger.debug(f"✅ {env_name}/{api_name} healthy")

            results.append(result)

        return results

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._service_cache or cache_key not in self._cache_expiry:
            return False
        return time.time() < self._cache_expiry[cache_key]

    def refresh_service_data(self):
        """Force refresh of service data."""
        self._service_cache.clear()
        self._cache_expiry.clear()
        logger.info("🔄 Precheck service data cache refreshed")

    def check_service_availability(self, service_name: str) -> bool:
        """Check if a specific service is available."""
        health_data = self.get_service_health()
        services = health_data.get('services', {})

        # Check exact match first
        if service_name in services:
            return services[service_name].get('status') == 'running'

        # Check partial matches
        for service_key, service_info in services.items():
            if service_name.lower() in service_key.lower():
                return service_info.get('status') == 'running'

        # Default to available if service not found
        return True


# Legacy compatibility - keep the original AzureServiceMonitor name
AzureServiceMonitor = PrecheckServiceMonitor
