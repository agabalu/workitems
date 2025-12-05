# core/integrations/prometheus_metrics_exporter.py
import time
import threading
from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server, CollectorRegistry, REGISTRY
    PROMETHEUS_CLIENT_AVAILABLE = True
except ImportError:
    PROMETHEUS_CLIENT_AVAILABLE = False
    logger.warning("prometheus_client not available")

class PrometheusMetricsExporter:
    """Prometheus metrics exporter for Universal Neural System with configuration integration"""

    def __init__(self, prometheus_endpoint: Union[str, int, None] = None, port: Optional[int] = None, registry: Optional[CollectorRegis
        """
        Initialize PrometheusMetricsExporter with flexible endpoint parsing

        Args:
            prometheus_endpoint: Can be:
                - "host:port" string (e.g., "10.223.251.30:32287")
                - port number as int (e.g., 32287)
                - service name from config (e.g., "metrics_exporter")
                - None (uses config or defaults)
            port: Explicit port number (overrides port from prometheus_endpoint)
            registry: Prometheus registry to use
        """
        # Parse endpoint to extract host and port
        self.host, self.port = self._parse_endpoint_with_config(prometheus_endpoint, port)

        self.registry = registry or (REGISTRY if PROMETHEUS_CLIENT_AVAILABLE else None)
        self.running = False
        self.server_thread = None
        self.metrics = {}

        if PROMETHEUS_CLIENT_AVAILABLE:
            self._initialize_metrics()
            logger.info(f"📊 Prometheus metrics initialized for {self.host}:{self.port}")
        else:
            logger.warning("Prometheus client not available - metrics will be simulated")

    def _parse_endpoint_with_config(self, prometheus_endpoint: Union[str, int, None], explicit_port: Optional[int]) -> tuple:
        """Parse endpoint configuration with config manager integration"""
        host = 'localhost'  # Default host
        port = 8001         # Default port

        try:
            # Try to load from configuration manager first
            try:
                from config.config_manager import config_manager

                # If prometheus_endpoint is a service name, look it up in config
                if isinstance(prometheus_endpoint, str) and ':' not in prometheus_endpoint and not prometheus_endpoint.isdigit():
                    service_config = config_manager.get_service(prometheus_endpoint)
                    if service_config:
                        host = service_config.host
                        port = service_config.port
                        logger.info(f"📋 Using config for service '{prometheus_endpoint}': {host}:{port}")
                        return host, port

                # Try to get metrics_exporter service as default
                if prometheus_endpoint is None:
                    metrics_service = config_manager.get_service('metrics_exporter')
                    if metrics_service:
                        host = metrics_service.host
                        port = metrics_service.port
                        logger.info(f"📋 Using default metrics_exporter config: {host}:{port}")
                        return host, port

            except ImportError:
                logger.debug("Config manager not available, using manual parsing")
            except Exception as e:
                logger.warning(f"Failed to load from config manager: {e}")

            # Manual parsing for direct endpoint specifications
            if explicit_port is not None:
                # Explicit port overrides everything
                port = int(explicit_port)
                if isinstance(prometheus_endpoint, str) and ':' not in prometheus_endpoint:
                    host = prometheus_endpoint
            elif isinstance(prometheus_endpoint, str) and ':' in prometheus_endpoint:
                # Format: "host:port"
                host_part, port_part = prometheus_endpoint.split(':', 1)
                host = host_part.strip()
                port = int(port_part.strip())
            elif isinstance(prometheus_endpoint, (int, str)) and str(prometheus_endpoint).isdigit():
                # Just port number
                port = int(prometheus_endpoint)
                # Try to get host from port registry if we only have port
                registry_host = self._get_host_from_port_registry(port)
                if registry_host:
                    host = registry_host
                    logger.info(f"📋 Found host in port registry: {host}:{port}")
            elif prometheus_endpoint is not None:
                # Try to use as host
                host = str(prometheus_endpoint)

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse endpoint '{prometheus_endpoint}': {e}. Using defaults.")
            host = 'localhost'
            port = 8001

        return host, port

    def _get_host_from_port_registry(self, target_port: int) -> Optional[str]:
        """Get host from port registry for a given port"""
        try:
            registry_file = "/etc/port-registry.conf"
            with open(registry_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        service_name, endpoint = line.split('=', 1)
                        if ':' in endpoint:
                            host, port_str = endpoint.split(':', 1)
                            if int(port_str) == target_port:
                                return host
        except Exception:
            pass
        return None

    def _initialize_metrics(self):
        """Initialize Prometheus metrics"""
        if not PROMETHEUS_CLIENT_AVAILABLE:
            return

        try:
            self.metrics = {
                'tasks_total': Counter(
                    'universal_neural_tasks_total',
                    'Total number of tasks processed',
                    ['domain', 'task_type', 'status'],
                    registry=self.registry
                ),
                'confidence_score': Gauge(
                    'universal_neural_confidence_score',
                    'Current confidence score',
                    ['domain'],
                    registry=self.registry
                ),
                'execution_time': Histogram(
                    'universal_neural_execution_time_seconds',
                    'Task execution time in seconds',
                    ['domain', 'task_type'],
                    registry=self.registry
                ),
                'system_health': Gauge(
                    'universal_neural_system_health',
                    'Overall system health score',
                    registry=self.registry
                ),
                'domains_mastered': Gauge(
                    'universal_neural_domains_mastered',
                    'Number of domains mastered',
                    registry=self.registry
                ),
                'active_tasks': Gauge(
                    'universal_neural_active_tasks',
                    'Number of currently active tasks',
                    registry=self.registry
                ),
                'learning_iterations': Counter(
                    'universal_neural_learning_iterations_total',
                    'Total number of learning iterations',
                    registry=self.registry
                )
            }
        except Exception as e:
            logger.error(f"Failed to initialize Prometheus metrics: {e}")
            self.metrics = {}

    def start_server(self) -> bool:
        """Start the Prometheus metrics server"""
        if not PROMETHEUS_CLIENT_AVAILABLE:
            logger.warning("Prometheus client not available - server not started")
            return False

        try:
            start_http_server(self.port, registry=self.registry)
            self.running = True
            logger.info(f"📈 Prometheus metrics server started on {self.host}:{self.port}")
            logger.info(f"📈 Metrics endpoint: http://{self.host}:{self.port}/metrics")
            return True
        except Exception as e:
            logger.error(f"Failed to start Prometheus server on {self.host}:{self.port}: {e}")
            return False

    def stop_server(self):
        """Stop the metrics server"""
        self.running = False
        logger.info(f"📊 Prometheus metrics server stopped ({self.host}:{self.port})")

    def update_metrics(self, universal_system):
        """Update metrics from universal system"""
        if not PROMETHEUS_CLIENT_AVAILABLE or not self.metrics:
            return

        try:
            status = universal_system.get_system_status()

            # Update system-level metrics
            if 'system_health' in self.metrics:
                self.metrics['system_health'].set(
                    status['system_health']['overall_score']
                )

            if 'domains_mastered' in self.metrics:
                self.metrics['domains_mastered'].set(
                    len(status['performance_metrics']['domains_mastered'])
                )

            if 'active_tasks' in self.metrics:
                self.metrics['active_tasks'].set(
                    status['active_tasks']
                )

            # Update domain-specific confidence scores
            if 'confidence_score' in self.metrics:
                for domain, expertise in status['domain_expertise'].items():
                    if expertise > 0:  # Only update domains with some expertise
                        self.metrics['confidence_score'].labels(domain=domain).set(expertise)

            logger.debug(f"📊 Prometheus metrics updated for {self.host}:{self.port}")

        except Exception as e:
            logger.warning(f"Failed to update Prometheus metrics: {e}")

    def record_task_completion(self, task, solution):
        """Record task completion metrics"""
        if not PROMETHEUS_CLIENT_AVAILABLE or not self.metrics:
            return

        try:
            # Record task completion
            if 'tasks_total' in self.metrics:
                status = 'success' if solution.confidence > 0.5 else 'low_confidence'
                self.metrics['tasks_total'].labels(
                    domain=task.domain.value,
                    task_type=task.task_type.value,
                    status=status
                ).inc()

            # Record execution time
            if 'execution_time' in self.metrics:
                self.metrics['execution_time'].labels(
                    domain=task.domain.value,
                    task_type=task.task_type.value
                ).observe(solution.execution_time)

        except Exception as e:
            logger.warning(f"Failed to record task metrics: {e}")

    def record_learning_iteration(self):
        """Record a learning iteration"""
        if not PROMETHEUS_CLIENT_AVAILABLE or not self.metrics:
            return

        try:
            if 'learning_iterations' in self.metrics:
                self.metrics['learning_iterations'].inc()
        except Exception as e:
            logger.warning(f"Failed to record learning iteration: {e}")

    def get_endpoint_info(self) -> Dict[str, Any]:
        """Get endpoint information"""
        return {
            'host': self.host,
            'port': self.port,
            'endpoint': f"{self.host}:{self.port}",
            'metrics_url': f"http://{self.host}:{self.port}/metrics",
            'running': self.running,
            'prometheus_available': PROMETHEUS_CLIENT_AVAILABLE
        }

    def __str__(self):
        return f"PrometheusMetricsExporter({self.host}:{self.port})"

    def __repr__(self):
        return f"PrometheusMetricsExporter(host='{self.host}', port={self.port}, running={self.running})"

    @classmethod
    def from_config(cls, service_name: str = 'metrics_exporter', **kwargs):
        """Create PrometheusMetricsExporter from configuration"""
        try:
            from config.config_manager import config_manager
            service_config = config_manager.get_service(service_name)
            if service_config:
                return cls(f"{service_config.host}:{service_config.port}", **kwargs)
        except Exception as e:
            logger.warning(f"Failed to create from config: {e}")

        # Fallback to default
        return cls(**kwargs)
