"""
Tests for the observability event bus.
"""

import threading
import time
from neugi_swarm_v2.observability.event_bus import EventBus, get_event_bus


def test_event_bus_basic():
    """Test basic publish/subscribe functionality."""
    bus = EventBus(max_history=10)
    results = []
    
    def handler(event):
        results.append(event.name)
    
    bus.subscribe('test_event', handler)
    bus.publish('test_event', {'data': 1})
    bus.publish('test_event', {'data': 2})
    
    assert len(results) == 2
    assert results[0] == 'test_event'
    assert results[1] == 'test_event'


def test_event_bus_middleware():
    """Test middleware functionality."""
    bus = EventBus(max_history=10)
    results = []
    middleware_calls = []
    
    def handler(event):
        results.append(event.name)
    
    def middleware(event):
        middleware_calls.append(event.name)
    
    bus.subscribe('test_event', handler)
    bus.add_middleware(middleware)
    
    bus.publish('test_event', {'data': 1})
    
    assert len(results) == 1
    assert results[0] == 'test_event'
    assert len(middleware_calls) == 1
    assert middleware_calls[0] == 'test_event'


def test_event_bus_history():
    """Test event history functionality."""
    bus = EventBus(max_history=5)
    
    bus.publish('event1', {'data': 1})
    bus.publish('event2', {'data': 2})
    bus.publish('event1', {'data': 3})
    
    history = bus.get_history()
    assert len(history) == 3
    
    history_event1 = bus.get_history('event1')
    assert len(history_event1) == 2
    
    history_event2 = bus.get_history('event2')
    assert len(history_event2) == 1


def test_event_bus_thread_safety():
    """Test that the event bus is thread-safe."""
    bus = EventBus(max_history=100)
    results = []
    results_lock = threading.Lock()
    
    def handler(event):
        with results_lock:
            results.append(event.name)
    
    def publish_events(thread_id):
        for i in range(10):
            bus.publish('thread_event', {'thread': thread_id, 'i': i})
    
    bus.subscribe('thread_event', handler)
    
    threads = []
    for i in range(5):
        t = threading.Thread(target=publish_events, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Should have 5 * 10 = 50 events
    assert len(results) == 50


def test_global_event_bus():
    """Test that the global event bus is accessible."""
    bus1 = get_event_bus()
    bus2 = get_event_bus()
    
    # Should be the same instance
    assert bus1 is bus2
    
    # Should be an EventBus
    assert isinstance(bus1, EventBus)


def test_middleware_error_isolation():
    """One bad middleware should not break other middleware or subscribers."""
    bus = EventBus(max_history=10)
    results = []

    def bad_middleware(event):
        raise RuntimeError("Intentional middleware failure")

    def good_middleware(event):
        results.append("mw:" + event.name)

    def subscriber(event):
        results.append("sub:" + event.name)

    bus.add_middleware(bad_middleware)
    bus.add_middleware(good_middleware)
    bus.subscribe('test', subscriber)

    bus.publish('test', {'data': 1})

    assert len(results) == 2
    assert results[0] == 'mw:test'
    assert results[1] == 'sub:test'
    print('OK: middleware error isolation')


def test_middleware_order():
    """Middleware should be called in order they were added."""
    bus = EventBus()
    calls = []

    def mw1(e):
        calls.append('mw1')

    def mw2(e):
        calls.append('mw2')

    def mw3(e):
        calls.append('mw3')

    bus.add_middleware(mw1)
    bus.add_middleware(mw2)
    bus.add_middleware(mw3)

    bus.publish('test', None)

    assert calls == ['mw1', 'mw2', 'mw3']
    print('OK: middleware order')


def test_subscriber_error_isolation():
    """One bad subscriber should not break other subscribers."""
    bus = EventBus(max_history=10)
    results = []

    def bad_sub(event):
        raise RuntimeError("Intentional subscriber failure")

    def good_sub(event):
        results.append(event.name)

    bus.subscribe('test', bad_sub)
    bus.subscribe('test', good_sub)

    bus.publish('test', {'data': 1})

    assert len(results) == 1
    assert results[0] == 'test'
    print('OK: subscriber error isolation')


def test_multiple_middleware():
    """Multiple middleware should all be called for each event."""
    bus = EventBus(max_history=10)
    calls = []

    def mw_a(e):
        calls.append('a')

    def mw_b(e):
        calls.append('b')

    bus.add_middleware(mw_a)
    bus.add_middleware(mw_b)

    bus.publish('e1', None)
    bus.publish('e2', None)

    assert calls == ['a', 'b', 'a', 'b']
    print('OK: multiple middleware')


if __name__ == '__main__':
    test_event_bus_basic()
    test_event_bus_middleware()
    test_event_bus_history()
    test_event_bus_thread_safety()
    test_global_event_bus()
    test_middleware_error_isolation()
    test_middleware_order()
    test_subscriber_error_isolation()
    test_multiple_middleware()
    print('All observability tests passed!')