"""
Authorization Gate for Autonomous Security Harness.
Blocks high-risk tools until approved.
"""
import logging
import time

logger = logging.getLogger(__name__)

class AuthGate:
    def __init__(self, db_session=None):
        """
        Initialize the authorization gate.

        Args:
            db_session: A database session or connection object for looking up approvals.
                        In a real implementation, this would be a database connection.
                        For this example, we'll use an in-memory dictionary to simulate.
        """
        # Risk levels for tools
        self.RISK_LEVELS = {
            'nmap': 'low',
            'dnsenum': 'low',
            'nuclei': 'medium',
            'sqlmap': 'high',
            'metasploit': 'critical',
            'hydra': 'high',
            'nikto': 'medium',  # We consider nikto medium risk
            'zap': 'medium'
        }

        # In-memory store for approvals (in production, this would be a database)
        # Format: {task_id: {tool: {user_id: approved_bool, timestamp: float}}}
        self.approvals = {}
        self.db_session = db_session  # Not used in this simple example

    def check_and_wait(self, task_id: str, tool: str, user_id: str, timeout: int = 3600) -> bool:
        """
        Check if the tool is approved for the given task and user.
        If not approved and the tool is high risk, wait for approval or timeout.

        Args:
            task_id: The ID of the task/workflow.
            tool: The name of the tool to check.
            user_id: The ID of the user requesting the tool use.
            timeout: Maximum time to wait for approval in seconds (default 1 hour).

        Returns:
            True if the tool is approved or low/medium risk, False if timeout or denied.

        Raises:
            TimeoutError: If approval is not received within the timeout period.
        """
        risk = self.RISK_LEVELS.get(tool, 'medium')

        # If risk is low or medium, we allow without explicit approval
        if risk not in ['high', 'critical']:
            logger.info(f"Tool {tool} has risk level {risk}, allowing without explicit approval.")
            return True

        # For high and critical risk tools, we require explicit approval
        logger.info(f"Tool {tool} has risk level {risk}, checking for approval.")

        # Check if we already have an approval record
        approval = self._get_approval(task_id, tool, user_id)
        if approval is not None:
            if approval:
                logger.info(f"Approval found for {tool} by user {user_id} in task {task_id}.")
                return True
            else:
                logger.warning(f"Explicit denial for {tool} by user {user_id} in task {task_id}.")
                return False

        # If we don't have an approval record, we need to wait for one.
        # In a real system, this would block and wait for an external approval (e.g., via a webhook).
        # For this example, we'll simulate by polling the in-memory store.
        # Note: This is a simplification. In reality, the auth gate would not block the workflow;
        # instead, it would set the state to wait for an external event.
        # However, for the sake of having a working example, we'll implement a simple wait.

        start_time = time.time()
        while time.time() - start_time < timeout:
            approval = self._get_approval(task_id, tool, user_id)
            if approval is not None:
                if approval:
                    logger.info(f"Approval received for {tool} by user {user_id} in task {task_id}.")
                    return True
                else:
                    logger.warning(f"Explicit denial received for {tool} by user {user_id} in task {task_id}.")
                    return False
            # Wait a bit before checking again
            time.sleep(5)

        # If we get here, we timed out
        logger.error(f"Approval timeout for {tool} by user {user_id} in task {task_id} after {timeout} seconds.")
        raise TimeoutError(f"No approval for tool {tool} after {timeout} seconds.")

    def _get_approval(self, task_id: str, tool: str, user_id: str) -> bool | None:
        """
        Retrieve the approval record for the given task, tool, and user.

        Returns:
            True if approved, False if denied, None if no record found.
        """
        # In our in-memory store:
        task_approvals = self.approvals.get(task_id, {})
        tool_approvals = task_approvals.get(tool, {})
        approval = tool_approvals.get(user_id, None)
        return approval

    def grant_approval(self, task_id: str, tool: str, user_id: str) -> None:
        """
        Grant approval for a tool for a given task and user.
        This would be called by an external system (e.g., a webhook from a UI).

        Args:
            task_id: The ID of the task/workflow.
            tool: The name of the tool to approve.
            user_id: The ID of the user granting the approval.
        """
        if task_id not in self.approvals:
            self.approvals[task_id] = {}
        if tool not in self.approvals[task_id]:
            self.approvals[task_id][tool] = {}
        self.approvals[task_id][tool][user_id] = True
        logger.info(f"Approval granted for {tool} by user {user_id} in task {task_id}.")

    def deny_approval(self, task_id: str, tool: str, user_id: str) -> None:
        """
        Deny approval for a tool for a given task and user.

        Args:
            task_id: The ID of the task/workflow.
            tool: The name of the tool to deny.
            user_id: The ID of the user denying the approval.
        """
        if task_id not in self.approvals:
            self.approvals[task_id] = {}
        if tool not in self.approvals[task_id]:
            self.approvals[task_id][tool] = {}
        self.approvals[task_id][tool][user_id] = False
        logger.info(f"Approval denied for {tool} by user {user_id} in task {task_id}.")
