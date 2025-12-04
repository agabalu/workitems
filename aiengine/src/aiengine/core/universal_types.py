"""
Shared types and classes for the Universal Neural System
This prevents circular imports between main.py and other modules
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

class DomainType(Enum):
    """Universal domain types the system can handle"""
    # Technology & Infrastructure
    INFRASTRUCTURE = "infrastructure"
    DEVOPS = "devops"
    CYBERSECURITY = "cybersecurity"
    CLOUD_COMPUTING = "cloud_computing"
    NETWORK_MANAGEMENT = "network_management"

    # Software Development & Quality Assurance
    SOFTWARE_QUALITY = "software_quality"
    BUILD_AUTOMATION = "build_automation"
    COMPLIANCE_MANAGEMENT = "compliance_management"
    INGREDIENT_VALIDATION = "ingredient_validation"

    # Precheck
    PRECHECK_VALIDATION = "precheck_validation"
    AZURE_INTEGRATION = "azure_integration"
    KUBERNETES_MANAGEMENT = "kubernetes_management"
    API_MONITORING = "api_monitoring"

    # Business & Finance
    FINANCE = "finance"
    TRADING = "trading"
    RISK_MANAGEMENT = "risk_management"
    SUPPLY_CHAIN = "supply_chain"
    CUSTOMER_SERVICE = "customer_service"

    # Healthcare & Life Sciences
    HEALTHCARE = "healthcare"
    MEDICAL_DIAGNOSIS = "medical_diagnosis"
    DRUG_DISCOVERY = "drug_discovery"
    GENOMICS = "genomics"

    # Science & Research
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"
    ASTRONOMY = "astronomy"
    CLIMATE_SCIENCE = "climate_science"

    # Engineering & Manufacturing
    MECHANICAL_ENGINEERING = "mechanical_engineering"
    ELECTRICAL_ENGINEERING = "electrical_engineering"
    CIVIL_ENGINEERING = "civil_engineering"
    MANUFACTURING = "manufacturing"
    ROBOTICS = "robotics"

    # Media & Content
    NATURAL_LANGUAGE = "natural_language"
    COMPUTER_VISION = "computer_vision"
    AUDIO_PROCESSING = "audio_processing"
    VIDEO_ANALYSIS = "video_analysis"
    CONTENT_GENERATION = "content_generation"

    # Social & Behavioral
    SOCIAL_MEDIA = "social_media"
    PSYCHOLOGY = "psychology"
    EDUCATION = "education"
    MARKETING = "marketing"

    # Transportation & Logistics
    TRANSPORTATION = "transportation"
    AUTONOMOUS_VEHICLES = "autonomous_vehicles"
    LOGISTICS = "logistics"

    # Energy & Environment
    ENERGY_MANAGEMENT = "energy_management"
    RENEWABLE_ENERGY = "renewable_energy"
    ENVIRONMENTAL_MONITORING = "environmental_monitoring"

    # Gaming & Entertainment
    GAMING = "gaming"
    ENTERTAINMENT = "entertainment"

    # Legal & Compliance
    LEGAL = "legal"
    COMPLIANCE = "compliance"

    # Agriculture & Food
    AGRICULTURE = "agriculture"
    FOOD_SCIENCE = "food_science"

    # Sports & Fitness
    SPORTS_ANALYTICS = "sports_analytics"
    FITNESS = "fitness"

    # Real Estate & Construction
    REAL_ESTATE = "real_estate"
    CONSTRUCTION = "construction"

    # Unknown/Generic
    UNKNOWN = "unknown"
    GENERIC = "generic"

class TaskType(Enum):
    """Universal task types"""
    # Prediction Tasks
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    TIME_SERIES_FORECASTING = "time_series_forecasting"
    ANOMALY_DETECTION = "anomaly_detection"

    # Precheck-specific tasks
    WAIVER_DECISION = "waiver_decision"
    EXCEPTION_ROUTING = "exception_routing"
    COMPLIANCE_VALIDATION = "compliance_validation"
    RISK_ASSESSMENT = "risk_assessment"
    APPROVAL_PREDICTION = "approval_prediction"
    PRECHECK_ANALYSIS = "precheck_analysis"
    PRECHECK_MONITORING_ = "precheck_monitoring"

    # Azure Integration
    AZURE_TOKEN_VALIDATION = "azure_token_validation"
    API_HEALTH_CHECK = "api_health_check"
    WEBHOOK_NOTIFICATION = "webhook_notification"

    # Kubernetes tasks
    DEPLOYMENT_HEALTH_CHECK = "deployment_health_check"
    DEPLOYMENT_RESTART = "deployment_restart"
    POD_ANOMALY_DETECTION = "pod_anomaly_detection"
    CLUSTER_MONITORING = "cluster_monitoring"

    # Generation Tasks
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    CODE_GENERATION = "code_generation"
    MUSIC_GENERATION = "music_generation"

    # Analysis Tasks
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"
    FEATURE_EXTRACTION = "feature_extraction"
    CLUSTERING = "clustering"

    # Optimization Tasks
    RESOURCE_OPTIMIZATION = "resource_optimization"
    ROUTE_OPTIMIZATION = "route_optimization"
    PARAMETER_TUNING = "parameter_tuning"
    SCHEDULING = "scheduling"

    # Decision Making
    RECOMMENDATION = "recommendation"
    DECISION_SUPPORT = "decision_support"
    POLICY_LEARNING = "policy_learning"
    STRATEGY_OPTIMIZATION = "strategy_optimization"

    # Processing Tasks
    DATA_PROCESSING = "data_processing"
    SIGNAL_PROCESSING = "signal_processing"
    IMAGE_PROCESSING = "image_processing"
    NATURAL_LANGUAGE_PROCESSING = "natural_language_processing"

    # Control Tasks
    CONTROL_SYSTEMS = "control_systems"
    AUTOMATION = "automation"
    MONITORING = "monitoring"

    # Learning Tasks
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    TRANSFER_LEARNING = "transfer_learning"
    META_LEARNING = "meta_learning"
    CONTINUAL_LEARNING = "continual_learning"

@dataclass
class UniversalTask:
    """Universal task representation"""
    task_id: str
    domain: DomainType
    task_type: TaskType
    input_data: Any
    expected_output: Optional[Any] = None
    metadata: Dict[str, Any] = None
    priority: int = 1
    timestamp: float = None
    user_id: str = "system"

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class PrecheckTaskData:
    """Specialized data structure for precheck tasks"""
    environment: str
    tenant_id: str
    app_client_id: str
    group_id: str
    api_endpoints: List[Dict[str, str]]
    client_secret_env: str
    webhook_config: Optional[Dict[str, Any]] = None
    monitoring_config: Optional[Dict[str, Any]] = None

@dataclass
class KubernetesTaskData:
    """Specialized data structure for Kubernetes tasks"""
    cluster_name: str
    namespace: str
    deployment_name: str
    action: str  # 'health_check', 'restart', 'monitor'
    monitor_rollout: bool = True
    timeout: int = 300

@dataclass
class UniversalSolution:
    """Universal solution representation with explainability"""
    task_id: str
    solution: Any
    confidence: float
    reasoning: str
    execution_time: float
    model_used: str
    domain_adapted: bool = False
    learned_patterns: List[str] = None

    # Explainability fields
    explanation: Dict[str, Any] = None
    feature_importance: Dict[str, float] = None
    attention_weights: List[float] = None
    decision_path: List[str] = None
    counterfactuals: List[Dict] = None
    uncertainty_analysis: Dict[str, float] = None

    def __post_init__(self):
        if self.learned_patterns is None:
            self.learned_patterns = []
        if self.explanation is None:
            self.explanation = {}
        if self.feature_importance is None:
            self.feature_importance = {}
        if self.attention_weights is None:
            self.attention_weights = []
        if self.decision_path is None:
            self.decision_path = []
        if self.counterfactuals is None:
            self.counterfactuals = []
        if self.uncertainty_analysis is None:
            self.uncertainty_analysis = {}
