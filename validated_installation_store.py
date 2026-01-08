"""
Validated installation store that checks workspace approval before saving
"""
import os
from typing import Optional
from slack_sdk.oauth.installation_store.installation_store import Installation, Bot
from sqlite_installation_store import SQLiteInstallationStore


class WorkspaceNotApprovedException(Exception):
    """Raised when a workspace is not approved for installation"""
    pass


class ValidatedInstallationStore(SQLiteInstallationStore):
    """
    Installation store that validates workspace against approved list before saving.

    Approved workspaces are configured via APPROVED_WORKSPACES environment variable
    as a comma-separated list of workspace names.
    """

    def __init__(self, database: str = "slack_installations.db"):
        super().__init__(database)
        self.approved_workspaces = self._load_approved_workspaces()

    def _load_approved_workspaces(self) -> set:
        """Load approved workspaces from environment variable"""
        approved = os.environ.get("APPROVED_WORKSPACES", "")

        if not approved:
            # If no approved list is set, allow all workspaces
            return None

        # Parse comma-separated values and strip whitespace
        workspaces = {ws.strip() for ws in approved.split(",") if ws.strip()}
        return workspaces

    def _is_workspace_approved(self, team_name: str) -> bool:
        """Check if workspace name is in approved list"""
        # If no approved list is configured, allow all
        if self.approved_workspaces is None:
            return True

        return team_name in self.approved_workspaces

    def save(self, installation: Installation):
        """Save installation after validating workspace approval"""
        team_name = installation.team_name or "Unknown Workspace"

        if not self._is_workspace_approved(team_name):
            raise WorkspaceNotApprovedException(
                f"Workspace '{team_name}' is not approved for this installation. "
                f"Please contact the app administrator for access."
            )

        # If approved, save normally
        super().save(installation)

    def find_installation(
        self,
        *,
        enterprise_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        is_enterprise_install: Optional[bool] = False,
    ) -> Optional[Installation]:
        """Find installation (no validation needed for retrieval)"""
        return super().find_installation(
            enterprise_id=enterprise_id,
            team_id=team_id,
            user_id=user_id,
            is_enterprise_install=is_enterprise_install
        )

    def find_bot(
        self,
        *,
        enterprise_id: Optional[str] = None,
        team_id: Optional[str] = None,
        is_enterprise_install: Optional[bool] = False,
    ) -> Optional[Bot]:
        """Find bot installation (no validation needed for retrieval)"""
        return super().find_bot(
            enterprise_id=enterprise_id,
            team_id=team_id,
            is_enterprise_install=is_enterprise_install
        )
