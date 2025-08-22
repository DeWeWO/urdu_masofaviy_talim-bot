import aiohttp
import httpx
import asyncio
import logging
from typing import Dict, List, Optional, Any
from aiohttp import ClientTimeout, ClientError
from data import config

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self):
        self.base_url = config.API_BASE_URL.rstrip("/")
        self.timeout = ClientTimeout(total=30, connect=10)
        self.session = None

    async def __aenter__(self):
        """Context manager uchun"""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager uchun"""
        if self.session:
            await self.session.close()

    async def request(self, method: str, endpoint: str, return_html=False, **kwargs) -> Optional[Dict[str, Any]]:
        """API ga umumiy so'rov yuborish"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Headers qo'shish
        headers = kwargs.get('headers', {})
        if not return_html and 'Accept' not in headers:
            headers.setdefault('Content-Type', 'application/json')
        kwargs['headers'] = headers

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.session is None:
                    # Agar context manager ishlatilmagan bo'lsa
                    async with aiohttp.ClientSession(timeout=self.timeout) as session:
                        async with session.request(method, url, **kwargs) as resp:
                            return await self._handle_response(resp, return_html)
                else:
                    # Context manager ishlatilgan bo'lsa
                    async with self.session.request(method, url, **kwargs) as resp:
                        return await self._handle_response(resp, return_html)

            except (ClientError, asyncio.TimeoutError):
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(1)

            except Exception:
                return None

    async def _handle_response(self, resp, return_html=False) -> Optional[Dict[str, Any]]:
        """Response ni qayta ishlash"""
        try:
            if resp.status == 204:  # No Content
                return {"success": True}
            
            if 200 <= resp.status < 300:
                if return_html:
                    return await resp.text()
                else:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        return await resp.json()
                    else:
                        return {"data": await resp.text()}
            else:
                return None
                
        except Exception:
            return None
    
    async def add_group(self, group_name: str, group_id: int) -> Optional[Dict]:
        payload = {
            "group_name": group_name,
            "group_id": group_id
        }
        return await self.request("POST", "telegram/group/add/", json=payload)
    
    async def add_register(
        self,
        telegram_id: int,
        group_id: int,
        username: Optional[str] = None,
        fio: Optional[str] = None,
        pnfl: Optional[str] = None,
        tg_tel: Optional[str] = None,
        tel: Optional[str] = None,
        parent_tel: Optional[str] = None,
        address: Optional[str] = None,
        is_active: bool = True
    ) -> Optional[Dict]:
        payload = {
            "telegram_id": telegram_id,
            "username": username,
            "fio": fio,
            "group_id": group_id,
            "pnfl": pnfl,
            "tg_tel": tg_tel,
            "tel": tel,
            "parent_tel": parent_tel,
            "address": address,
            "is_active": is_active,
        }
        # None qiymatlarni yubormaslik uchun filtr
        payload = {k: v for k, v in payload.items() if v is not None}
        
        return await self.request("POST", "register/", json=payload)

    
api_client = APIClient()