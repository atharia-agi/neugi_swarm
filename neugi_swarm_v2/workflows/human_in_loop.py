"""HumanInTheLoop: Human approval and intervention system.

Provides pause points, approval gates, state modification, and
notification system for workflows requiring human input.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class PausePointType(Enum):
    """Type of pause point in the workflow."""
    APPROVAL = "approval"
    INPUT = "input"
    REVIEW = "review"
    OVERRIDE = "override"


@dataclass
class HumanResponse:
    """Response from a human operator.

    Attributes:
        request_id: ID of the request being responded to.
        status: Approval status.
        comment: Optional comment from the human.
        state_modifications: Optional state changes to apply.
        responded_at: Timestamp of response.
        responder: Optional identifier of the responder.
    """

    request_id: str
    status: ApprovalStatus
    comment: Optional[str] = None
    state_modifications: Optional[Dict[str, Any]] = None
    responded_at: float = field(default_factory=time.time)
    responder: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "comment": self.comment,
            "state_modifications": self.state_modifications,
            "responded_at": self.responded_at,
            "responder": self.responder,
        }


@dataclass
class ApprovalRequest:
    """A request for human approval or input.

    Attributes:
        request_id: Unique identifier for the request.
        node_name: Node that triggered the request.
        pause_type: Type of pause point.
        prompt: Message to show the human.
        state_snapshot: Current workflow state at pause.
        timeout: Timeout in seconds for response.
        created_at: Timestamp when request was created.
        status: Current status of the request.
        response: Human response if received.
        metadata: Additional context for the request.
    """

    request_id: str
    node_name: str
    pause_type: PausePointType
    prompt: str
    state_snapshot: Dict[str, Any]
    timeout: float = 300.0
    created_at: float = field(default_factory=time.time)
    status: ApprovalStatus = ApprovalStatus.PENDING
    response: Optional[HumanResponse] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the request has timed out."""
        if self.status != ApprovalStatus.PENDING:
            return False
        return (time.time() - self.created_at) > self.timeout

    @property
    def time_remaining(self) -> float:
        """Get remaining time before timeout."""
        if self.status != ApprovalStatus.PENDING:
            return 0.0
        remaining = self.timeout - (time.time() - self.created_at)
        return max(0.0, remaining)

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "request_id": self.request_id,
            "node_name": self.node_name,
            "pause_type": self.pause_type.value,
            "prompt": self.prompt,
            "state_snapshot": self.state_snapshot,
            "timeout": self.timeout,
            "created_at": self.created_at,
            "status": self.status.value,
            "response": self.response.to_dict() if self.response else None,
            "metadata": self.metadata,
        }


@dataclass
class PausePoint:
    """Definition of a pause point in the workflow.

    Attributes:
        name: Unique identifier for the pause point.
        node_name: Node where the pause occurs.
        pause_type: Type of pause.
        prompt: Message to show when paused.
        timeout: Timeout in seconds.
        required_roles: Roles that can respond to this pause.
        auto_approve_conditions: Conditions for automatic approval.
    """

    name: str
    node_name: str
    pause_type: PausePointType
    prompt: str
    timeout: float = 300.0
    required_roles: Set[str] = field(default_factory=set)
    auto_approve_conditions: Optional[Callable[[Dict[str, Any]], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def should_auto_approve(self, state: Dict[str, Any]) -> bool:
        """Check if this pause should be auto-approved based on state.

        Args:
            state: Current workflow state.

        Returns:
            True if auto-approval conditions are met.
        """
        if self.auto_approve_conditions is None:
            return False
        try:
            return self.auto_approve_conditions(state)
        except Exception:
            return False


class NotificationHandler:
    """Handles notifications for pending approval requests.

    Provides a pluggable notification system that can be extended
    with email, Slack, webhook, or other notification channels.
    """

    def __init__(self) -> None:
        """Initialize the notification handler."""
        self._handlers: List[Callable[[ApprovalRequest], None]] = []

    def register_handler(
        self,
        handler: Callable[[ApprovalRequest], None],
    ) -> "NotificationHandler":
        """Register a notification handler.

        Args:
            handler: Function that receives ApprovalRequest.

        Returns:
            Self for method chaining.
        """
        self._handlers.append(handler)
        return self

    def notify(self, request: ApprovalRequest) -> None:
        """Send notifications for a new approval request.

        Args:
            request: The approval request to notify about.
        """
        for handler in self._handlers:
            try:
                handler(request)
            except Exception:
                pass  # Don't let notification failures block workflow

    def notify_timeout(self, request: ApprovalRequest) -> None:
        """Send notifications for a timed-out request.

        Args:
            request: The timed-out approval request.
        """
        for handler in self._handlers:
            try:
                handler(request)
            except Exception:
                pass


class HumanInTheLoop:
    """Manages human-in-the-loop interactions for workflows.

    Provides pause points, approval gates, state modification,
    and timeout handling for workflows requiring human input.

    Example:
        hil = HumanInTheLoop()
        hil.add_approval_point("review_node", "Please review the results")
        request = hil.create_request("review_node", state)
        hil.approve(request.request_id, "Looks good")
    """

    def __init__(
        self,
        notifications: Optional[NotificationHandler] = None,
    ) -> None:
        """Initialize the human-in-the-loop system.

        Args:
            notifications: Optional notification handler.
        """
        self.notifications = notifications or NotificationHandler()
        self._pause_points: Dict[str, PausePoint] = {}
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._completed_requests: Dict[str, ApprovalRequest] = {}
        self._response_callbacks: List[Callable[[HumanResponse], None]] = []

    def add_pause_point(
        self,
        name: str,
        node_name: str,
        pause_type: PausePointType = PausePointType.APPROVAL,
        prompt: str = "Please review and approve",
        timeout: float = 300.0,
        required_roles: Optional[Set[str]] = None,
        auto_approve_conditions: Optional[Callable[[Dict[str, Any]], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "HumanInTheLoop":
        """Add a pause point to the workflow.

        Args:
            name: Unique identifier for the pause point.
            node_name: Node where the pause occurs.
            pause_type: Type of pause.
            prompt: Message to show when paused.
            timeout: Timeout in seconds.
            required_roles: Roles that can respond.
            auto_approve_conditions: Conditions for auto-approval.
            metadata: Additional metadata.

        Returns:
            Self for method chaining.
        """
        pause = PausePoint(
            name=name,
            node_name=node_name,
            pause_type=pause_type,
            prompt=prompt,
            timeout=timeout,
            required_roles=required_roles or set(),
            auto_approve_conditions=auto_approve_conditions,
            metadata=metadata or {},
        )
        self._pause_points[name] = pause
        return self

    def add_approval_gate(
        self,
        name: str,
        node_name: str,
        prompt: str = "Please approve this step",
        timeout: float = 300.0,
    ) -> "HumanInTheLoop":
        """Add an approval gate (shorthand for approval pause point).

        Args:
            name: Unique identifier.
            node_name: Node where the gate is.
            prompt: Approval prompt.
            timeout: Timeout in seconds.

        Returns:
            Self for method chaining.
        """
        return self.add_pause_point(
            name=name,
            node_name=node_name,
            pause_type=PausePointType.APPROVAL,
            prompt=prompt,
            timeout=timeout,
        )

    def add_input_request(
        self,
        name: str,
        node_name: str,
        prompt: str = "Please provide input",
        timeout: float = 300.0,
    ) -> "HumanInTheLoop":
        """Add an input request pause point.

        Args:
            name: Unique identifier.
            node_name: Node where input is needed.
            prompt: Input prompt.
            timeout: Timeout in seconds.

        Returns:
            Self for method chaining.
        """
        return self.add_pause_point(
            name=name,
            node_name=node_name,
            pause_type=PausePointType.INPUT,
            prompt=prompt,
            timeout=timeout,
        )

    def create_request(
        self,
        pause_point_name: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ApprovalRequest]:
        """Create an approval request for a pause point.

        Args:
            pause_point_name: Name of the pause point.
            state: Current workflow state.
            metadata: Additional metadata.

        Returns:
            ApprovalRequest if pause point exists, None otherwise.
        """
        pause = self._pause_points.get(pause_point_name)
        if not pause:
            return None

        # Check auto-approval conditions
        if pause.should_auto_approve(state):
            request = ApprovalRequest(
                request_id=str(uuid.uuid4()),
                node_name=pause.node_name,
                pause_type=pause.pause_type,
                prompt=pause.prompt,
                state_snapshot=state,
                timeout=pause.timeout,
                status=ApprovalStatus.APPROVED,
                metadata=metadata or {},
            )
            self._completed_requests[request.request_id] = request
            return request

        # Create pending request
        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            node_name=pause.node_name,
            pause_type=pause.pause_type,
            prompt=pause.prompt,
            state_snapshot=state,
            timeout=pause.timeout,
            metadata=metadata or {},
        )

        self._pending_requests[request.request_id] = request

        # Send notifications
        self.notifications.notify(request)

        return request

    def approve(
        self,
        request_id: str,
        comment: Optional[str] = None,
        responder: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Approve a pending request.

        Args:
            request_id: ID of the request to approve.
            comment: Optional approval comment.
            responder: Optional responder identifier.

        Returns:
            Updated ApprovalRequest if found, None otherwise.
        """
        return self._respond_to_request(
            request_id,
            ApprovalStatus.APPROVED,
            comment=comment,
            responder=responder,
        )

    def reject(
        self,
        request_id: str,
        comment: Optional[str] = None,
        responder: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Reject a pending request.

        Args:
            request_id: ID of the request to reject.
            comment: Optional rejection comment.
            responder: Optional responder identifier.

        Returns:
            Updated ApprovalRequest if found, None otherwise.
        """
        return self._respond_to_request(
            request_id,
            ApprovalStatus.REJECTED,
            comment=comment,
            responder=responder,
        )

    def modify_and_approve(
        self,
        request_id: str,
        state_modifications: Dict[str, Any],
        comment: Optional[str] = None,
        responder: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Approve with state modifications.

        Args:
            request_id: ID of the request.
            state_modifications: State changes to apply.
            comment: Optional comment.
            responder: Optional responder identifier.

        Returns:
            Updated ApprovalRequest if found, None otherwise.
        """
        return self._respond_to_request(
            request_id,
            ApprovalStatus.MODIFIED,
            state_modifications=state_modifications,
            comment=comment,
            responder=responder,
        )

    def provide_input(
        self,
        request_id: str,
        input_data: Dict[str, Any],
        comment: Optional[str] = None,
        responder: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Provide input for an input request.

        Args:
            request_id: ID of the request.
            input_data: Input data to provide.
            comment: Optional comment.
            responder: Optional responder identifier.

        Returns:
            Updated ApprovalRequest if found, None otherwise.
        """
        return self._respond_to_request(
            request_id,
            ApprovalStatus.APPROVED,
            state_modifications=input_data,
            comment=comment,
            responder=responder,
        )

    def override_decision(
        self,
        request_id: str,
        new_status: ApprovalStatus,
        state_modifications: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
        responder: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Override a previous decision.

        Args:
            request_id: ID of the request to override.
            new_status: New status to set.
            state_modifications: Optional state changes.
            comment: Optional comment.
            responder: Optional responder identifier.

        Returns:
            Updated ApprovalRequest if found, None otherwise.
        """
        request = self._completed_requests.get(request_id)
        if not request:
            return None

        response = HumanResponse(
            request_id=request_id,
            status=new_status,
            comment=comment,
            state_modifications=state_modifications,
            responder=responder,
        )

        request.status = new_status
        request.response = response

        # Move back to pending if needed for re-processing
        if new_status == ApprovalStatus.PENDING:
            self._pending_requests[request_id] = request
            self._completed_requests.pop(request_id, None)

        return request

    def check_timeouts(self) -> List[ApprovalRequest]:
        """Check for timed-out requests and update their status.

        Returns:
            List of requests that timed out.
        """
        timed_out = []

        for request_id, request in list(self._pending_requests.items()):
            if request.is_expired:
                request.status = ApprovalStatus.TIMED_OUT
                request.response = HumanResponse(
                    request_id=request_id,
                    status=ApprovalStatus.TIMED_OUT,
                    comment="Request timed out",
                )
                timed_out.append(request)

                # Move to completed
                self._completed_requests[request_id] = request
                del self._pending_requests[request_id]

                # Notify about timeout
                self.notifications.notify_timeout(request)

        return timed_out

    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending requests.

        Returns:
            List of pending ApprovalRequest objects.
        """
        # Update timeouts first
        self.check_timeouts()
        return list(self._pending_requests.values())

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get a request by ID.

        Args:
            request_id: Request ID.

        Returns:
            ApprovalRequest if found, None otherwise.
        """
        return (
            self._pending_requests.get(request_id)
            or self._completed_requests.get(request_id)
        )

    def get_requests_for_node(self, node_name: str) -> List[ApprovalRequest]:
        """Get all requests for a specific node.

        Args:
            node_name: Node name.

        Returns:
            List of ApprovalRequest objects.
        """
        all_requests = list(self._pending_requests.values()) + list(
            self._completed_requests.values()
        )
        return [r for r in all_requests if r.node_name == node_name]

    def register_response_callback(
        self,
        callback: Callable[[HumanResponse], None],
    ) -> "HumanInTheLoop":
        """Register a callback for when responses are received.

        Args:
            callback: Function that receives HumanResponse.

        Returns:
            Self for method chaining.
        """
        self._response_callbacks.append(callback)
        return self

    def wait_for_response(
        self,
        request_id: str,
        poll_interval: float = 1.0,
    ) -> Optional[HumanResponse]:
        """Block and wait for a response to a request.

        Args:
            request_id: Request to wait for.
            poll_interval: How often to check for response.

        Returns:
            HumanResponse when received, None if timed out.
        """
        while True:
            request = self.get_request(request_id)
            if not request:
                return None

            if request.status != ApprovalStatus.PENDING:
                return request.response

            time.sleep(poll_interval)

    def _respond_to_request(
        self,
        request_id: str,
        status: ApprovalStatus,
        state_modifications: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
        responder: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Internal method to respond to a request.

        Args:
            request_id: Request ID.
            status: Response status.
            state_modifications: Optional state changes.
            comment: Optional comment.
            responder: Optional responder identifier.

        Returns:
            Updated ApprovalRequest if found, None otherwise.
        """
        request = self._pending_requests.get(request_id)
        if not request:
            return None

        response = HumanResponse(
            request_id=request_id,
            status=status,
            comment=comment,
            state_modifications=state_modifications,
            responder=responder,
        )

        request.status = status
        request.response = response

        # Move from pending to completed
        self._completed_requests[request_id] = request
        del self._pending_requests[request_id]

        # Invoke callbacks
        for callback in self._response_callbacks:
            try:
                callback(response)
            except Exception:
                pass

        return request

    def clear_completed(self, older_than: Optional[float] = None) -> int:
        """Clear completed requests.

        Args:
            older_than: Optional timestamp. Only clear requests older than this.

        Returns:
            Number of requests cleared.
        """
        if older_than is None:
            count = len(self._completed_requests)
            self._completed_requests.clear()
            return count

        to_remove = [
            rid for rid, req in self._completed_requests.items()
            if req.created_at < older_than
        ]
        for rid in to_remove:
            del self._completed_requests[rid]
        return len(to_remove)

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about requests.

        Returns:
            Dictionary with request statistics.
        """
        all_requests = list(self._pending_requests.values()) + list(
            self._completed_requests.values()
        )

        status_counts: Dict[str, int] = {}
        for req in all_requests:
            status = req.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total": len(all_requests),
            "pending": len(self._pending_requests),
            "completed": len(self._completed_requests),
            "by_status": status_counts,
        }
