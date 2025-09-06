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
                    logger.error(f"API request failed after {max_retries} attempts: {url}")
                    return None
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Unexpected error during API request: {e}")
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
                logger.error(f"API returned error status {resp.status}: {await resp.text()}")
                return None
                
        except Exception as e:
            logger.error(f"Error handling response: {e}")
            return None
    
    async def add_group(self, group_name: str, group_id: int) -> Optional[Dict]:
        payload = {
            "group_name": group_name,
            "group_id": group_id
        }
        logger.info(f"Adding group: {group_name} (ID: {group_id})")
        return await self.request("POST", "telegram/group/add/", json=payload)
    
    async def add_register(
        self,
        telegram_id: int,
        group_ids: List[int],
        username: Optional[str] = None,
        fio: Optional[str] = None,
        hemis_id: Optional[int] = None,
        pnfl: Optional[str] = None,
        tg_tel: Optional[str] = None,
        tel: Optional[str] = None,
        parent_tel: Optional[str] = None,
        address: Optional[str] = None,
        is_active: bool = False,
        is_teacher: bool = False,
    ) -> Optional[Dict]:
        payload = {
            "telegram_id": telegram_id,
            "username": username,
            "fio": fio,
            "group_ids": group_ids,  # ✅ TO'G'RI - backend "group_ids" kutadi
            "hemis_id": hemis_id if hemis_id is not None else None,
            "pnfl": pnfl,
            "tg_tel": tg_tel,
            "tel": tel,
            "parent_tel": parent_tel,
            "address": address,
            "is_active": is_active,
            "is_teacher": is_teacher,
        }
        
        # Bo'sh qiymatlarni olib tashlash
        payload = {k: v for k, v in payload.items() if v is not None and v != ""}
        
        logger.info(f"Adding register for user {telegram_id} to groups {group_ids}")
        return await self.request("POST", "register/", json=payload)
    
    async def update_register(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        fio: Optional[str] = None,
        hemis_id: Optional[int] = None,
        pnfl: Optional[str] = None,
        tg_tel: Optional[str] = None,
        tel: Optional[str] = None,
        parent_tel: Optional[str] = None,
        address: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_teacher: Optional[bool] = None,
        group_ids: Optional[List[int]] = None,
    ) -> Optional[Dict]:
        payload = {
            "username": username,
            "fio": fio,
            "hemis_id": hemis_id if hemis_id is not None else None,
            "pnfl": pnfl,
            "tg_tel": tg_tel,
            "tel": tel,
            "parent_tel": parent_tel,
            "address": address,
            "is_active": is_active,
            "is_teacher": is_teacher,
            "group_ids": group_ids,  # ✅ TO'G'RI
        }
        
        filtered_payload = {}
        for k, v in payload.items():
            if v is not None and v != "":
                if isinstance(v, str) and not v.strip():
                    continue
                filtered_payload[k] = v
            elif isinstance(v, bool):
                filtered_payload[k] = v
                
        logger.info(f"Updating register for user {telegram_id}")
        return await self.request("PATCH", f"register/{telegram_id}/", json=filtered_payload)
    
    async def get_all_users_basic_info(self) -> Optional[Dict]:
        """Barcha foydalanuvchilarning telegram_id va pnfl ma'lumotlarini olish"""
        return await self.request("GET", "users/basic-info/")

    async def check_user_status(self, telegram_id: int) -> Optional[Dict]:
        """Telegram ID bo'yicha foydalanuvchi holatini tekshirish"""
        return await self.request("GET", f"users/check-status/{telegram_id}/")

    async def get_users_by_status(self) -> Optional[Dict]:
        """Status bo'yicha foydalanuvchilarni olish"""
        return await self.request("GET", "users/by-status/")

    async def get_user_full_info(self, telegram_id: int) -> Optional[Dict]:
        """Foydalanuvchining to'liq ma'lumotlarini olish"""
        return await self.request("GET", f"users/{telegram_id}/")
    
    async def add_member_activity(
        self,
        telegram_id: int,
        group_id: int,
        activity_type: str,  # 'join', 'leave', 'kicked', 'removed'
        action_by: str,      # 'self', 'admin', 'system', 'invite_link'
        activity_time: str,  # ISO format: "2025-09-06T13:30:25"
        admin_telegram_id: Optional[int] = None,
        admin_name: Optional[str] = None,
        admin_username: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict]:
        """A'zo faoliyatini backend ga yuborish"""
        payload = {
            "telegram_id": telegram_id,
            "group_id": group_id,
            "activity_type": activity_type,
            "action_by": action_by,
            "activity_time": activity_time,
        }
        
        # Ixtiyoriy maydonlar
        if admin_telegram_id:
            payload["admin_telegram_id"] = admin_telegram_id
        if admin_name:
            payload["admin_name"] = admin_name
        if admin_username:
            payload["admin_username"] = admin_username
        if notes:
            payload["notes"] = notes
        
        # Bo'sh qiymatlarni olib tashlash
        payload = {k: v for k, v in payload.items() if v is not None and v != ""}
        
        logger.info(f"Adding member activity: {activity_type} for user {telegram_id} in group {group_id}")
        return await self.request("POST", "member-activity/add/", json=payload)


    async def get_member_activities(
        self,
        telegram_id: Optional[int] = None,
        group_id: Optional[int] = None,
        activity_type: Optional[str] = None,
        date_from: Optional[str] = None,  # 'YYYY-MM-DD'
        date_to: Optional[str] = None,    # 'YYYY-MM-DD'
    ) -> Optional[Dict]:
        """A'zo faoliyatlari ro'yxatini olish"""
        params = {}
        
        if telegram_id:
            params["telegram_id"] = telegram_id
        if group_id:
            params["group_id"] = group_id
        if activity_type:
            params["activity_type"] = activity_type
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        
        logger.info(f"Getting member activities with params: {params}")
        return await self.request("GET", "member-activity/list/", params=params)


    async def get_member_activity_stats(self) -> Optional[Dict]:
        """A'zo faoliyatlari statistikasi"""
        logger.info("Getting member activity statistics")
        return await self.request("GET", "member-activity/stats/")

    
api_client = APIClient()