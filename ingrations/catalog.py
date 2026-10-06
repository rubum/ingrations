import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from ingrations.models import AppSpec, ActionSpec

logger = logging.getLogger("ingrations.catalog")


class Catalog:
    """
    Manages loading, caching, indexing, and lookup of AppSpec and ActionSpec definitions.
    """

    def __init__(self, catalog_dir: Optional[Path] = None):
        self.catalog_dir = self._resolve_catalog_dir(catalog_dir)
        self._apps: Dict[str, AppSpec] = {}
        self._actions: Dict[str, ActionSpec] = {}
        self._categories: Dict[str, List[str]] = {}
        self._loaded: bool = False

    def _resolve_catalog_dir(self, custom_path: Optional[Path]) -> Path:
        if custom_path and custom_path.exists():
            return custom_path
        # Look alongside package
        pkg_root = Path(__file__).resolve().parent.parent / "catalog"
        if pkg_root.exists() and (pkg_root / "index.json").exists():
            return pkg_root
        # User home fallback
        user_catalog = Path.home() / ".ingrations" / "catalog"
        return user_catalog

    def load(self, force_reload: bool = False) -> None:
        """Loads all app and action specifications from the catalog directory."""
        if self._loaded and not force_reload:
            return

        if not self.catalog_dir.exists():
            logger.debug(f"Catalog directory '{self.catalog_dir}' does not exist.")
            self._loaded = True
            return

        index_file = self.catalog_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                for item in index_data.get("apps", []):
                    rel_file = item.get("file")
                    if rel_file:
                        app_path = self.catalog_dir / rel_file
                        if app_path.exists():
                            self._load_app_file(app_path)
            except Exception as e:
                logger.error(f"Error loading catalog index '{index_file}': {e}")
        else:
            # Discover recursively
            for p in self.catalog_dir.glob("**/*.json"):
                if p.name != "index.json":
                    self._load_app_file(p)

        self._loaded = True

    def _load_app_file(self, file_path: Path) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            app = AppSpec.model_validate(data)
            self.register_app(app)
        except Exception as e:
            logger.warning(f"Failed to load app spec from '{file_path}': {e}")

    def register_app(self, app: AppSpec) -> None:
        """Registers an AppSpec in-memory, updating category and action indexes."""
        self._apps[app.id] = app
        self._categories.setdefault(app.category, [])
        if app.id not in self._categories[app.category]:
            self._categories[app.category].append(app.id)

        for action in app.actions:
            self._actions[action.id] = action

    def list_apps(self, category: Optional[str] = None) -> List[AppSpec]:
        """Lists available apps, optionally filtered by category."""
        self.load()
        if category:
            app_ids = self._categories.get(category.lower(), [])
            return [self._apps[aid] for aid in app_ids if aid in self._apps]
        return list(self._apps.values())

    def get_app(self, app_id: str) -> Optional[AppSpec]:
        """Retrieves AppSpec by ID."""
        self.load()
        return self._apps.get(app_id.lower())

    def get_action(self, action_id: str) -> Optional[ActionSpec]:
        """Retrieves ActionSpec by ID (e.g. 'github.create_issue')."""
        self.load()
        return self._actions.get(action_id)

    def list_actions(self, app_id: Optional[str] = None, category: Optional[str] = None) -> List[ActionSpec]:
        """Lists actions, optionally filtered by app or category."""
        self.load()
        if app_id:
            app = self.get_app(app_id)
            return app.actions if app else []
        if category:
            apps = self.list_apps(category)
            actions = []
            for a in apps:
                actions.extend(a.actions)
            return actions
        return list(self._actions.values())

    @property
    def total_apps(self) -> int:
        self.load()
        return len(self._apps)

    @property
    def total_actions(self) -> int:
        self.load()
        return len(self._actions)


# Global singleton instance
default_catalog = Catalog()
