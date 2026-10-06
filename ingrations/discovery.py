import re
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from ingrations.models import SearchResult, ActionSpec, AppSpec
from ingrations.catalog import Catalog, default_catalog

logger = logging.getLogger("ingrations.discovery")


class ToolDiscoveryEngine:
    """
    Sub-millisecond semantic tool discovery engine backed by in-memory SQLite FTS5.
    Enables agents to query across 15,000+ actions with zero prompt bloat.
    """

    def __init__(self, catalog: Optional[Catalog] = None):
        self.catalog = catalog or default_catalog
        self._db: Optional[sqlite3.Connection] = None
        self._indexed: bool = False
        self._init_db()

    def _init_db(self) -> None:
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute("PRAGMA synchronous = OFF;")
        self._db.execute("PRAGMA journal_mode = MEMORY;")
        self._db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS tool_index USING fts5(
                action_id UNINDEXED,
                app_id,
                action_name,
                app_name,
                description,
                category,
                tags,
                tokenize = 'porter unicode61'
            );
        """)
        self._db.commit()

    def build_index(self, force: bool = False) -> int:
        """Indexes all actions from the catalog into the FTS5 virtual table."""
        if self._indexed and not force:
            return 0

        self.catalog.load()
        apps = self.catalog.list_apps()

        self._db.execute("DELETE FROM tool_index;")
        count = 0

        for app in apps:
            for action in app.actions:
                tags_str = " ".join(action.tags)
                self._db.execute("""
                    INSERT INTO tool_index (
                        action_id, app_id, action_name, app_name, description, category, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    action.id,
                    app.id,
                    action.name,
                    app.name,
                    action.description,
                    app.category,
                    tags_str
                ))
                count += 1

        self._db.commit()
        self._indexed = True
        logger.debug(f"Indexed {count} actions across {len(apps)} apps in FTS5 engine.")
        return count

    def search(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Executes an FTS5 BM25-ranked full-text search.
        Falls back to prefix/LIKE matching if query contains syntax edge cases.
        """
        if not self._indexed:
            self.build_index()

        clean_query = query.strip()
        if not clean_query:
            return []

        # Sanitize query for FTS5 (escape special chars)
        sanitized_tokens = re.findall(r"[A-Za-z0-9_]+", clean_query)
        if not sanitized_tokens:
            return []

        fts_match_expr = " OR ".join(f'"{t}"*' for t in sanitized_tokens)

        results: List[SearchResult] = []
        try:
            if category:
                cursor = self._db.execute("""
                    SELECT action_id, app_id, action_name, app_name, description, category, tags, bm25(tool_index) as rank
                    FROM tool_index
                    WHERE tool_index MATCH ? AND category = ?
                    ORDER BY rank ASC
                    LIMIT ?;
                """, (fts_match_expr, category.lower(), limit))
            else:
                cursor = self._db.execute("""
                    SELECT action_id, app_id, action_name, app_name, description, category, tags, bm25(tool_index) as rank
                    FROM tool_index
                    WHERE tool_index MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?;
                """, (fts_match_expr, limit))

            rows = cursor.fetchall()
            for r in rows:
                action_id, app_id, action_name, app_name, desc, cat, tags_str, rank = r
                tags = tags_str.split() if tags_str else []
                # Invert BM25 score so higher is better
                norm_score = max(0.0, 10.0 - float(rank))
                results.append(SearchResult(
                    action_id=action_id,
                    app_id=app_id,
                    action_name=action_name,
                    app_name=app_name,
                    description=desc,
                    category=cat,
                    score=norm_score,
                    tags=tags
                ))

        except Exception as e:
            logger.warning(f"FTS5 match failed for '{clean_query}': {e}. Falling back to LIKE.")
            # Fallback LIKE query
            wildcard = f"%{clean_query}%"
            cursor = self._db.execute("""
                SELECT action_id, app_id, action_name, app_name, description, category, tags
                FROM tool_index
                WHERE action_name LIKE ? OR description LIKE ? OR app_name LIKE ?
                LIMIT ?;
            """, (wildcard, wildcard, wildcard, limit))
            for r in cursor.fetchall():
                action_id, app_id, action_name, app_name, desc, cat, tags_str = r
                results.append(SearchResult(
                    action_id=action_id,
                    app_id=app_id,
                    action_name=action_name,
                    app_name=app_name,
                    description=desc,
                    category=cat,
                    score=1.0,
                    tags=tags_str.split() if tags_str else []
                ))

        return results

    @staticmethod
    def get_search_tool_declaration() -> Dict[str, Any]:
        """Returns standard JSON Schema declaration for the meta-tool `ingrations_search_tools`."""
        return {
            "name": "ingrations_search_tools",
            "description": "Searches for external software integrations, APIs, and tools across 1,500+ apps (e.g. GitHub, Jira, Slack, Linear, Notion, Stripe, Sentry, AWS). Returns matching actions and parameter schemas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language action or tool keywords (e.g. 'create github pull request', 'send slack message', 'linear issue status', 'stripe customer charge')"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter: devtools, productivity, cloud, crm_finance",
                        "enum": ["devtools", "productivity", "cloud", "crm_finance"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tools to return (default: 5, max: 10)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }


# Global singleton engine
default_discovery = ToolDiscoveryEngine()
