"""
Async HTTP utilities for NEUGI channels.
============================================
Provides async HTTP requests with fallback to thread executor.

Usage:
    from channels.async_http import AsyncHTTPClient
    
    client = AsyncHTTPClient()
    result = await client.post("https://api.example.com", json={"key": "value"})
    
    # Or as context manager
    async with AsyncHTTPClient() as client:
        result = await client.get("https://api.example.com")
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AsyncHTTPClient:
    """
    Async HTTP client with aiohttp preferred, requests fallback.
    
    Automatically detects available backend:
        1. aiohttp (truly async, preferred)
        2. requests + asyncio.to_thread (fallback)
    """

    def __init__(self):
        self._aiohttp = None
        self._session = None
        self._backend = "unknown"
        self._init_backend()

    def _init_backend(self):
        """Detect best available HTTP backend."""
        try:
            import aiohttp
            self._aiohttp = aiohttp
            self._backend = "aiohttp"
            logger.debug("Using aiohttp for async HTTP")
        except ImportError:
            self._backend = "requests_thread"
            logger.debug("aiohttp not available, using requests in thread executor")

    async def __aenter__(self):
        if self._backend == "aiohttp":
            self._session = self._aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
            self._session = None

    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Make async HTTP request."""
        if self._backend == "aiohttp":
            return await self._request_aiohttp(method, url, headers, json_data, data, timeout)
        else:
            return await self._request_thread(method, url, headers, json_data, data, timeout)

    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        return await self.request("GET", url, headers=headers, timeout=timeout)

    async def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        return await self.request("POST", url, headers=headers, json_data=json_data, data=data, timeout=timeout)

    async def download(
        self,
        url: str,
        timeout: int = 60,
    ) -> bytes:
        """Download binary content."""
        if self._backend == "aiohttp":
            if not self._session:
                self._session = self._aiohttp.ClientSession()
            async with self._session.get(url, timeout=self._aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                return await resp.read()
        else:
            import requests
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: requests.get(url, timeout=timeout)
            )
            resp.raise_for_status()
            return resp.content

    async def _request_aiohttp(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]],
        json_data: Optional[Dict[str, Any]],
        data: Optional[Any],
        timeout: int,
    ) -> Dict[str, Any]:
        """Make request using aiohttp."""
        if not self._session:
            self._session = self._aiohttp.ClientSession()
        
        kwargs = {}
        if headers:
            kwargs["headers"] = headers
        if json_data:
            kwargs["json"] = json_data
        if data:
            kwargs["data"] = data
        
        async with self._session.request(
            method, url,
            timeout=self._aiohttp.ClientTimeout(total=timeout),
            **kwargs
        ) as resp:
            text = await resp.text()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"ok": False, "description": text, "status_code": resp.status}

    async def _request_thread(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]],
        json_data: Optional[Dict[str, Any]],
        data: Optional[Any],
        timeout: int,
    ) -> Dict[str, Any]:
        """Make request using requests in thread executor."""
        import requests
        
        def _do_request():
            kwargs = {"timeout": timeout}
            if headers:
                kwargs["headers"] = headers
            if json_data:
                kwargs["json"] = json_data
            if data:
                kwargs["data"] = data
            
            if method == "GET":
                return requests.get(url, **kwargs)
            elif method == "POST":
                return requests.post(url, **kwargs)
            else:
                return requests.request(method, url, **kwargs)
        
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, _do_request)
        
        try:
            return resp.json()
        except Exception:
            return {"ok": False, "description": resp.text, "status_code": resp.status_code}


__all__ = ["AsyncHTTPClient"]
