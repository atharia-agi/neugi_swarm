"""
Middleware examples for NEUGI Event Bus.
These examples demonstrate how to use the middleware functionality
added to the event bus in v2.1.2.
"""

from neugi_swarm_v2.observability.event_bus import Event, get_event_bus


def timing_middleware(event: Event) -> None:
    """
    Example middleware that measures event processing time.
    This would typically be used with more sophisticated tracking.
    """
    # In a real implementation, you might store timing data
    # or send it to a metrics system
    pass


def logging_middleware(event: Event) -> None:
    """
    Example middleware that logs events.
    """
    print(f"[EVENT] {event.name} from {event.source or 'unknown'} at {event.timestamp}")


def error_tracking_middleware(event: Event) -> None:
    """
    Example middleware that tracks events related to errors.
    """
    if "error" in event.name.lower() or "failure" in event.name.lower():
        # In a real implementation, you might increment error counters
        # or send alerts for failure events
        pass


def setup_example_middleware() -> None:
    """
    Setup example middleware on the global event bus.
    """
    bus = get_event_bus()

    # Add middleware - these will be called for every event published
    bus.add_middleware(timing_middleware)
    bus.add_middleware(logging_middleware)
    bus.add_middleware(error_tracking_middleware)

    print("Example middleware installed on event bus")


# Example usage
if __name__ == "__main__":
    # Setup middleware
    setup_example_middleware()

    # Get the event bus
    bus = get_event_bus()

    # Define a simple handler
    def my_event_handler(event: Event) -> None:
        print(f"[HANDLER] Received event: {event.name}")

    # Subscribe to events
    bus.subscribe("tool_execution_success", my_event_handler)
    bus.subscribe("tool_execution_failure", my_event_handler)

    # Publish some test events
    bus.publish("tool_execution_success", {
        "tool": "web_search",
        "query": "NEUGI Swarm",
        "duration_ms": 1250
    }, source="ToolExecutor")

    bus.publish("tool_execution_failure", {
        "tool": "system_execute_command",
        "command": "invalid_command",
        "error": "Command not found"
    }, source="ToolExecutor")

    # Show event history
    history = bus.get_history()
    print(f"\nEvent history contains {len(history)} events")

    # Show history for specific event type
    success_events = bus.get_history("tool_execution_success")
    print(f"Success events: {len(success_events)}")

    failure_events = bus.get_history("tool_execution_failure")
    print(f"Failure events: {len(failure_events)}")
