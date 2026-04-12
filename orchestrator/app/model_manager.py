"""
Memory-aware model manager for orchestrator.
Automatically manages model loading/unloading based on available memory.
Supports multi-user sessions with intelligent model caching.
"""

import os
import psutil
import time
from typing import Dict, Any, Optional
from pathlib import Path

# Model metadata: size in MB when loaded in memory
MODEL_MEMORY_MAP = {
    "tinyllama": {"size_mb": 1200, "tier": "ultra_light"},
    "tinyllama:latest": {"size_mb": 1200, "tier": "ultra_light"},
    "phi3": {"size_mb": 4000, "tier": "fast"},
    "phi3:latest": {"size_mb": 4000, "tier": "fast"},
    "mistral": {"size_mb": 6000, "tier": "capable"},
    "mistral:7b": {"size_mb": 6000, "tier": "capable"},
    "llama3": {"size_mb": 6500, "tier": "capable"},
    "llama3:8b": {"size_mb": 6500, "tier": "capable"},
}

# Reserved memory for system and other services (MB)
SYSTEM_RESERVE_MB = 500  # OS, Python orchestrator, etc.
BUFFER_MB = 200  # Safety buffer for spikes


class ModelMemoryManager:
    """Manages model loading/unloading with intelligent memory eviction."""

    def __init__(self, auto_manage: bool = True):
        self.auto_manage = auto_manage
        self.loaded_models: Dict[str, Dict[str, Any]] = {}
        self.model_usage: Dict[str, float] = {}  # model_name -> last_used_timestamp
        self.session_model_affinity: Dict[str, str] = {}  # session_id -> preferred_model

    def get_available_memory_mb(self) -> int:
        """Get available system memory in MB."""
        mem = psutil.virtual_memory()
        available_mb = mem.available // (1024 * 1024)
        return available_mb

    def get_memory_utilization(self) -> Dict[str, Any]:
        """Get current memory usage stats."""
        mem = psutil.virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        used_mb = mem.used // (1024 * 1024)
        available_mb = mem.available // (1024 * 1024)

        return {
            "total_mb": total_mb,
            "used_mb": used_mb,
            "available_mb": available_mb,
            "percent": mem.percent,
            "recommended_action": self._get_memory_recommendation(available_mb, total_mb),
        }

    def _get_memory_recommendation(self, available_mb: int, total_mb: int) -> str:
        """Recommend memory actions based on usage."""
        if available_mb < SYSTEM_RESERVE_MB + BUFFER_MB:
            return "CRITICAL: Unload largest model immediately"
        elif available_mb < (SYSTEM_RESERVE_MB + BUFFER_MB + 1500):
            return "WARNING: Consider unloading large models"
        elif total_mb < 8192:
            return "INFO: 8GB total—recommend upgrading to 12GB for multi-user"
        else:
            return "OK: Sufficient memory"

    def can_load_model(self, model_name: str) -> bool:
        """Check if model can fit in available memory."""
        model_info = MODEL_MEMORY_MAP.get(model_name)
        if not model_info:
            return False

        needed_mb = model_info["size_mb"]
        available_mb = self.get_available_memory_mb()

        # Need: model size + system reserve + buffer
        required_mb = needed_mb + SYSTEM_RESERVE_MB + BUFFER_MB

        return available_mb > required_mb

    def mark_model_used(self, model_name: str) -> None:
        """Track model usage for LRU eviction."""
        self.model_usage[model_name] = time.time()

    def get_lru_candidates_for_eviction(self) -> list:
        """Get models that should be unloaded (LRU order)."""
        # Sort by last used time (oldest first)
        sorted_models = sorted(self.model_usage.items(), key=lambda x: x[1])
        
        candidates = []
        for model_name, _ in sorted_models:
            if model_name in self.loaded_models:
                model_info = MODEL_MEMORY_MAP.get(model_name, {})
                candidates.append({
                    "model": model_name,
                    "size_mb": model_info.get("size_mb", 0),
                    "tier": model_info.get("tier", "unknown"),
                })
        
        return candidates

    def ensure_model_available(self, model_name: str, required_for_session: Optional[str] = None) -> bool:
        """
        Attempt to make model available, evicting others if necessary.
        Returns True if model is available, False if it cannot be loaded.
        """
        if model_name in self.loaded_models:
            self.mark_model_used(model_name)
            return True

        # Track session affinity
        if required_for_session:
            self.session_model_affinity[required_for_session] = model_name

        # Check if model fits
        if self.can_load_model(model_name):
            self.loaded_models[model_name] = {
                "loaded_at": time.time(),
                "tier": MODEL_MEMORY_MAP.get(model_name, {}).get("tier"),
            }
            self.mark_model_used(model_name)
            return True

        # If no space, evict LRU models until it fits
        if self.auto_manage:
            candidates = self.get_lru_candidates_for_eviction()
            
            # Prefer evicting ultra-light/fast models first, keep capable models if possible
            candidates.sort(key=lambda x: (x["tier"] != "ultra_light", x["size_mb"]))

            freed_mb = 0
            model_info = MODEL_MEMORY_MAP.get(model_name, {})
            needed_mb = model_info.get("size_mb", 0)
            required_mb = needed_mb + SYSTEM_RESERVE_MB + BUFFER_MB

            for candidate in candidates:
                if candidate["model"] != model_name:
                    freed_mb += candidate["size_mb"]
                    del self.loaded_models[candidate["model"]]
                    self.model_usage.pop(candidate["model"], None)

                if self.get_available_memory_mb() > required_mb:
                    self.loaded_models[model_name] = {
                        "loaded_at": time.time(),
                        "tier": MODEL_MEMORY_MAP.get(model_name, {}).get("tier"),
                    }
                    self.mark_model_used(model_name)
                    return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive memory and model status."""
        mem = self.get_memory_utilization()
        loaded_models_list = []
        
        for model_name, info in self.loaded_models.items():
            model_info = MODEL_MEMORY_MAP.get(model_name, {})
            loaded_models_list.append({
                "model": model_name,
                "size_mb": model_info.get("size_mb", 0),
                "tier": info.get("tier"),
                "loaded_at": info.get("loaded_at"),
                "last_used": self.model_usage.get(model_name),
            })

        return {
            "memory": mem,
            "loaded_models": loaded_models_list,
            "model_count": len(self.loaded_models),
            "lru_candidates": self.get_lru_candidates_for_eviction(),
            "session_affinity": self.session_model_affinity,
        }


# Global instance
_model_manager: Optional[ModelMemoryManager] = None


def get_model_manager() -> ModelMemoryManager:
    """Get or create the global model manager."""
    global _model_manager
    if _model_manager is None:
        auto_manage = os.getenv("ORCHESTRATOR_AUTO_MANAGE_MODELS", "true").lower() == "true"
        _model_manager = ModelMemoryManager(auto_manage=auto_manage)
    return _model_manager
