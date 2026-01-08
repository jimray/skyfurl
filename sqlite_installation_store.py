"""
SQLite-based installation store for Slack OAuth tokens
"""
import sqlite3
import json
from typing import Optional
from pathlib import Path
from slack_sdk.oauth.installation_store import InstallationStore
from slack_sdk.oauth.installation_store.installation_store import Installation, Bot


class SQLiteInstallationStore(InstallationStore):
    """
    SQLite implementation of Slack's InstallationStore.

    Stores OAuth installation data (bot tokens, user tokens, team info) in SQLite.
    """

    def __init__(self, database: str = "slack_installations.db"):
        """
        Initialize SQLite installation store

        Args:
            database: Path to SQLite database file
        """
        self.database = database
        self._init_db()

    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()

        # Create installations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS installations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                enterprise_id TEXT,
                enterprise_name TEXT,
                enterprise_url TEXT,
                team_id TEXT NOT NULL,
                team_name TEXT,
                bot_token TEXT,
                bot_id TEXT,
                bot_user_id TEXT,
                bot_scopes TEXT,
                bot_refresh_token TEXT,
                bot_token_expires_at INTEGER,
                user_id TEXT,
                user_token TEXT,
                user_scopes TEXT,
                user_refresh_token TEXT,
                user_token_expires_at INTEGER,
                incoming_webhook_url TEXT,
                incoming_webhook_channel TEXT,
                incoming_webhook_channel_id TEXT,
                incoming_webhook_configuration_url TEXT,
                is_enterprise_install INTEGER,
                token_type TEXT,
                installed_at INTEGER NOT NULL,
                UNIQUE(client_id, enterprise_id, team_id, user_id)
            )
        """)

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_team_id
            ON installations(team_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_enterprise_team
            ON installations(enterprise_id, team_id)
        """)

        conn.commit()
        conn.close()

    def save(self, installation: Installation):
        """Save installation data to SQLite"""
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO installations (
                client_id, app_id, enterprise_id, enterprise_name, enterprise_url,
                team_id, team_name, bot_token, bot_id, bot_user_id, bot_scopes,
                bot_refresh_token, bot_token_expires_at, user_id, user_token,
                user_scopes, user_refresh_token, user_token_expires_at,
                incoming_webhook_url, incoming_webhook_channel,
                incoming_webhook_channel_id, incoming_webhook_configuration_url,
                is_enterprise_install, token_type, installed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            installation.client_id,
            installation.app_id,
            installation.enterprise_id,
            installation.enterprise_name,
            installation.enterprise_url,
            installation.team_id,
            installation.team_name,
            installation.bot_token,
            installation.bot_id,
            installation.bot_user_id,
            json.dumps(installation.bot_scopes) if installation.bot_scopes else None,
            installation.bot_refresh_token,
            installation.bot_token_expires_at,
            installation.user_id,
            installation.user_token,
            json.dumps(installation.user_scopes) if installation.user_scopes else None,
            installation.user_refresh_token,
            installation.user_token_expires_at,
            installation.incoming_webhook_url,
            installation.incoming_webhook_channel,
            installation.incoming_webhook_channel_id,
            installation.incoming_webhook_configuration_url,
            1 if installation.is_enterprise_install else 0,
            installation.token_type,
            installation.installed_at
        ))

        conn.commit()
        conn.close()

    def find_installation(
        self,
        *,
        enterprise_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        is_enterprise_install: Optional[bool] = False,
    ) -> Optional[Installation]:
        """Find installation by team/enterprise/user"""
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM installations WHERE 1=1"
        params = []

        if enterprise_id:
            query += " AND enterprise_id = ?"
            params.append(enterprise_id)

        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY installed_at DESC LIMIT 1"

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_installation(row)

        return None

    def find_bot(
        self,
        *,
        enterprise_id: Optional[str] = None,
        team_id: Optional[str] = None,
        is_enterprise_install: Optional[bool] = False,
    ) -> Optional[Bot]:
        """Find bot installation"""
        installation = self.find_installation(
            enterprise_id=enterprise_id,
            team_id=team_id,
            is_enterprise_install=is_enterprise_install
        )

        if installation and installation.bot_token:
            return Bot(
                app_id=installation.app_id,
                enterprise_id=installation.enterprise_id,
                enterprise_name=installation.enterprise_name,
                team_id=installation.team_id,
                team_name=installation.team_name,
                bot_token=installation.bot_token,
                bot_id=installation.bot_id,
                bot_user_id=installation.bot_user_id,
                bot_scopes=installation.bot_scopes,
                bot_refresh_token=installation.bot_refresh_token,
                bot_token_expires_at=installation.bot_token_expires_at,
                is_enterprise_install=installation.is_enterprise_install,
                installed_at=installation.installed_at,
            )

        return None

    def delete_installation(
        self,
        *,
        enterprise_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Delete installation from database"""
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()

        query = "DELETE FROM installations WHERE 1=1"
        params = []

        if enterprise_id:
            query += " AND enterprise_id = ?"
            params.append(enterprise_id)

        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        cursor.execute(query, params)
        conn.commit()
        conn.close()

    def delete_bot(
        self,
        *,
        enterprise_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ):
        """Delete bot installation"""
        self.delete_installation(
            enterprise_id=enterprise_id,
            team_id=team_id
        )

    def _row_to_installation(self, row: sqlite3.Row) -> Installation:
        """Convert database row to Installation object"""
        return Installation(
            app_id=row['app_id'],
            enterprise_id=row['enterprise_id'],
            enterprise_name=row['enterprise_name'],
            enterprise_url=row['enterprise_url'],
            team_id=row['team_id'],
            team_name=row['team_name'],
            bot_token=row['bot_token'],
            bot_id=row['bot_id'],
            bot_user_id=row['bot_user_id'],
            bot_scopes=json.loads(row['bot_scopes']) if row['bot_scopes'] else [],
            bot_refresh_token=row['bot_refresh_token'],
            bot_token_expires_at=row['bot_token_expires_at'],
            user_id=row['user_id'],
            user_token=row['user_token'],
            user_scopes=json.loads(row['user_scopes']) if row['user_scopes'] else [],
            user_refresh_token=row['user_refresh_token'],
            user_token_expires_at=row['user_token_expires_at'],
            incoming_webhook_url=row['incoming_webhook_url'],
            incoming_webhook_channel=row['incoming_webhook_channel'],
            incoming_webhook_channel_id=row['incoming_webhook_channel_id'],
            incoming_webhook_configuration_url=row['incoming_webhook_configuration_url'],
            is_enterprise_install=bool(row['is_enterprise_install']),
            token_type=row['token_type'],
            installed_at=row['installed_at'],
        )
