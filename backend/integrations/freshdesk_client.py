"""
Bobby — Freshdesk Client
========================
Async REST client for Freshdesk API v2.

Handles:
- Authentication
- Ticket creation
- Ticket retrieval
- Ticket updates
- Notes
- Ticket search
- Rate-limit retry
- Domain normalization
- API error logging
- In-memory fallback when credentials are missing
"""

from __future__ import annotations

import httpx
import structlog

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from config.settings import settings


logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Freshdesk mappings
# ---------------------------------------------------------------------------

PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "urgent": 4,
}

STATUS_MAP = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
}


# ---------------------------------------------------------------------------
# Custom exception for rate limiting
# ---------------------------------------------------------------------------

class FreshdeskRateLimitError(Exception):
    """Raised when Freshdesk returns HTTP 429."""

    def __init__(self, message: str = "Freshdesk API rate limit exceeded"):
        super().__init__(message)


# ---------------------------------------------------------------------------
# Freshdesk API Client
# ---------------------------------------------------------------------------

class FreshdeskClient:
    """Async Freshdesk API v2 client."""

    def __init__(self, api_key: str, domain: str):

        # ---------------------------------------------------------------
        # Normalize domain
        # ---------------------------------------------------------------

        domain = (domain or "").strip()

        domain = domain.removeprefix("https://")
        domain = domain.removeprefix("http://")
        domain = domain.rstrip("/")

        self.domain = domain

        self.base_url = f"https://{domain}/api/v2"

        self.auth = (
            api_key.strip(),
            "X",
        )

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info(
            "freshdesk.client_initialized",
            domain=self.domain,
            base_url=self.base_url,
        )

    # -------------------------------------------------------------------
    # Generic API request
    # -------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=2,
            max=10,
        ),
        retry=retry_if_exception(
            lambda exc: isinstance(exc, FreshdeskRateLimitError)
        ),
    )
    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict | list:

        url = f"{self.base_url}{path}"

        logger.info(
            "freshdesk.request",
            method=method,
            url=url,
        )

        try:

            async with httpx.AsyncClient(
                timeout=15.0
            ) as client:

                response = await client.request(
                    method=method,
                    url=url,
                    auth=self.auth,
                    headers=self.headers,
                    **kwargs,
                )

        except httpx.ConnectError as exc:

            logger.error(
                "freshdesk.connection_error",
                method=method,
                url=url,
                error=str(exc),
            )

            raise

        except httpx.TimeoutException as exc:

            logger.error(
                "freshdesk.timeout",
                method=method,
                url=url,
                error=str(exc),
            )

            raise

        except httpx.RequestError as exc:

            logger.error(
                "freshdesk.request_error",
                method=method,
                url=url,
                error=str(exc),
            )

            raise

        # ---------------------------------------------------------------
        # Log Freshdesk response
        # ---------------------------------------------------------------

        logger.info(
            "freshdesk.response",
            method=method,
            url=url,
            status_code=response.status_code,
            response_body=response.text[:2000],
        )

        # ---------------------------------------------------------------
        # Rate limiting
        # ---------------------------------------------------------------

        if response.status_code == 429:

            logger.warning(
                "freshdesk.rate_limited",
                url=url,
                retry_after=response.headers.get("Retry-After"),
            )

            raise FreshdeskRateLimitError()

        # ---------------------------------------------------------------
        # HTTP errors
        # ---------------------------------------------------------------

        if response.is_error:

            logger.error(
                "freshdesk.api_error",
                method=method,
                url=url,
                status_code=response.status_code,
                response_body=response.text[:2000],
            )

            # Preserve the actual Freshdesk error.
            raise httpx.HTTPStatusError(
                f"Freshdesk API returned {response.status_code}: "
                f"{response.text[:2000]}",
                request=response.request,
                response=response,
            )

        # ---------------------------------------------------------------
        # Successful response
        # ---------------------------------------------------------------

        if not response.text:
            return {}

        try:
            return response.json()

        except ValueError:

            logger.error(
                "freshdesk.invalid_json",
                url=url,
                response_body=response.text[:2000],
            )

            return {}

    # -------------------------------------------------------------------
    # CREATE TICKET
    # -------------------------------------------------------------------

    async def create_ticket(
        self,
        subject: str,
        description: str,
        category: str = "IT",
        priority: str = "medium",
        requester_id: str = "",
    ) -> dict:
        """Create a new Freshdesk ticket."""

        # Normalize priority
        priority = (priority or "medium").lower().strip()

        priority_value = PRIORITY_MAP.get(
            priority,
            PRIORITY_MAP["medium"],
        )

        # Normalize category
        category = (category or "IT").strip()

        # ---------------------------------------------------------------
        # Freshdesk ticket payload
        # ---------------------------------------------------------------

        payload = {
            "subject": subject or "IT Support",
            "description": description or "",
            "priority": priority_value,
            "status": 2,
            "tags": [
                "bobby-ai",
                category.lower(),
            ],
        }

        # ---------------------------------------------------------------
        # Requester email
        #
        # requester_id is currently being used by Bobby as the user's
        # email address.
        # ---------------------------------------------------------------

        if requester_id:

            requester_email = requester_id.strip()

            if requester_email:

                payload["email"] = requester_email

        # ---------------------------------------------------------------
        # Logging
        # ---------------------------------------------------------------

        logger.info(
            "freshdesk.create_ticket",
            subject=payload["subject"],
            category=category,
            priority=priority,
            requester_email=payload.get("email"),
            payload=payload,
        )

        # ---------------------------------------------------------------
        # Create ticket
        # ---------------------------------------------------------------

        try:

            result = await self._request(
                "POST",
                "/tickets",
                json=payload,
            )

        except Exception as exc:

            logger.error(
                "freshdesk.create_ticket_failed",
                subject=payload["subject"],
                error=str(exc),
                error_type=type(exc).__name__,
            )

            raise

        # ---------------------------------------------------------------
        # Validate response
        # ---------------------------------------------------------------

        if not isinstance(result, dict):

            logger.error(
                "freshdesk.invalid_ticket_response",
                response_type=type(result).__name__,
                response=result,
            )

            raise ValueError(
                "Freshdesk returned an unexpected ticket response."
            )

        ticket_id = result.get("id")

        logger.info(
            "freshdesk.ticket_created",
            ticket_id=ticket_id,
            subject=result.get("subject"),
        )

        return result

    # -------------------------------------------------------------------
    # GET SINGLE TICKET
    # -------------------------------------------------------------------

    async def get_ticket(
        self,
        ticket_id: str,
    ) -> dict:

        result = await self._request(
            "GET",
            f"/tickets/{ticket_id}",
        )

        return self._format_ticket(result)

    # -------------------------------------------------------------------
    # GET TICKETS BY USER
    # -------------------------------------------------------------------

    async def get_tickets_by_user(
        self,
        user_email: str,
        status: str | None = None,
    ) -> list[dict]:

        params = {
            "per_page": 10,
        }

        if user_email:

            params["email"] = user_email.strip()

        if status:

            status = status.lower().strip()

            status_code = {
                "open": 2,
                "pending": 3,
                "resolved": 4,
                "closed": 5,
            }.get(status)

            if status_code:

                params["status"] = status_code

        results = await self._request(
            "GET",
            "/tickets",
            params=params,
        )

        if isinstance(results, list):

            return [
                self._format_ticket(ticket)
                for ticket in results
            ]

        return []

    # -------------------------------------------------------------------
    # UPDATE TICKET
    # -------------------------------------------------------------------

    async def update_ticket(
        self,
        ticket_id: str,
        updates: dict,
    ) -> dict:

        logger.info(
            "freshdesk.update_ticket",
            ticket_id=ticket_id,
            updates=updates,
        )

        return await self._request(
            "PUT",
            f"/tickets/{ticket_id}",
            json=updates,
        )

    # -------------------------------------------------------------------
    # ADD NOTE
    # -------------------------------------------------------------------

    async def add_note(
        self,
        ticket_id: str,
        body: str,
        private: bool = True,
    ) -> dict:

        logger.info(
            "freshdesk.add_note",
            ticket_id=ticket_id,
            private=private,
        )

        return await self._request(
            "POST",
            f"/tickets/{ticket_id}/notes",
            json={
                "body": body,
                "private": private,
            },
        )

    # -------------------------------------------------------------------
    # SEARCH TICKETS
    # -------------------------------------------------------------------

    async def search_tickets(
        self,
        query: str,
    ) -> list[dict]:

        results = await self._request(
            "GET",
            "/tickets/search",
            params={
                "query": f'"{query}"'
            },
        )

        tickets = (
            results.get("results", [])
            if isinstance(results, dict)
            else []
        )

        return [
            self._format_ticket(ticket)
            for ticket in tickets
        ]

    # -------------------------------------------------------------------
    # FORMAT TICKET
    # -------------------------------------------------------------------

    @staticmethod
    def _format_ticket(
        ticket: dict,
    ) -> dict:

        return {
            "id": ticket.get("id"),
            "subject": ticket.get("subject"),
            "description": ticket.get(
                "description_text",
                ticket.get("description", ""),
            ),
            "status": STATUS_MAP.get(
                ticket.get("status"),
                "Unknown",
            ),
            "priority": ticket.get("priority"),
            "created_at": ticket.get("created_at"),
            "updated_at": ticket.get("updated_at"),
            "tags": ticket.get("tags", []),
        }


# ---------------------------------------------------------------------------
# In-Memory Freshdesk Client
# ---------------------------------------------------------------------------

class InMemoryFreshdeskClient:
    """Mock Freshdesk client used when credentials are unavailable."""

    def __init__(self):

        self.tickets = {}
        self.counter = 1000

    async def create_ticket(
        self,
        subject: str,
        description: str,
        category: str = "IT",
        priority: str = "medium",
        requester_id: str = "",
    ) -> dict:

        self.counter += 1

        ticket_id = self.counter

        ticket = {
            "id": ticket_id,
            "subject": subject,
            "description": description,
            "status": 2,
            "priority": PRIORITY_MAP.get(
                priority,
                2,
            ),
            "created_at": "2026-08-14T08:00:00Z",
            "updated_at": "2026-08-14T08:00:00Z",
            "tags": [
                "bobby-ai",
                category.lower(),
            ],
        }

        self.tickets[str(ticket_id)] = ticket

        logger.info(
            "mock_freshdesk.create_ticket",
            ticket_id=ticket_id,
            subject=subject,
        )

        return ticket

    async def get_ticket(
        self,
        ticket_id: str,
    ) -> dict:

        ticket = self.tickets.get(
            str(ticket_id)
        )

        if not ticket:

            ticket = {
                "id": (
                    int(ticket_id)
                    if ticket_id.isdigit()
                    else 4521
                ),
                "subject": (
                    "Server downtime incident"
                    if not ticket_id.isdigit()
                    else "Mock Ticket"
                ),
                "description": "Mock Description",
                "status": (
                    3
                    if not ticket_id.isdigit()
                    else 2
                ),
                "priority": 2,
                "created_at": "2026-08-14T08:00:00Z",
                "updated_at": "2026-08-14T08:00:00Z",
                "tags": [],
            }

        return self._format_ticket(ticket)

    async def get_tickets_by_user(
        self,
        user_email: str,
        status: str | None = None,
    ) -> list[dict]:

        results = list(
            self.tickets.values()
        )

        if not results:

            results = [
                {
                    "id": 4521,
                    "subject": "Server downtime incident",
                    "description_text": "HR server downtime issue.",
                    "status": 3,
                    "priority": 2,
                    "created_at": "2026-08-14T06:00:00Z",
                    "updated_at": "2026-08-14T06:00:00Z",
                    "tags": ["bobby-ai"],
                }
            ]

        return [
            self._format_ticket(ticket)
            for ticket in results
        ]

    async def update_ticket(
        self,
        ticket_id: str,
        updates: dict,
    ) -> dict:

        tid = str(ticket_id)

        if tid in self.tickets:

            self.tickets[tid].update(updates)

            if (
                "priority" in updates
                and isinstance(
                    updates["priority"],
                    str,
                )
            ):

                self.tickets[tid]["priority"] = (
                    PRIORITY_MAP.get(
                        updates["priority"],
                        2,
                    )
                )

            return self.tickets[tid]

        mock_ticket = {
            "id": (
                int(ticket_id)
                if ticket_id.isdigit()
                else 4521
            ),
            "subject": "Server downtime incident",
            "description": "HR server downtime issue.",
            "status": 3,
            "priority": (
                PRIORITY_MAP.get(
                    updates.get("priority"),
                    2,
                )
                if "priority" in updates
                else 2
            ),
            "created_at": "2026-08-14T06:00:00Z",
            "updated_at": "2026-08-14T08:00:00Z",
            "tags": ["bobby-ai"],
        }

        return mock_ticket

    async def add_note(
        self,
        ticket_id: str,
        body: str,
        private: bool = True,
    ) -> dict:

        return {
            "id": 12345,
            "body": body,
        }

    @staticmethod
    def _format_ticket(
        ticket: dict,
    ) -> dict:

        return {
            "id": ticket.get("id"),
            "subject": ticket.get("subject"),
            "description": ticket.get(
                "description",
                "",
            ),
            "status": STATUS_MAP.get(
                ticket.get("status", 2),
                "Open",
            ),
            "priority": ticket.get(
                "priority",
                2,
            ),
            "created_at": ticket.get(
                "created_at"
            ),
            "updated_at": ticket.get(
                "updated_at"
            ),
            "tags": ticket.get(
                "tags",
                [],
            ),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_freshdesk_instance = None


def get_freshdesk_client():
    """
    Return the shared Freshdesk client.

    Uses the real Freshdesk API when valid credentials
    are available. Otherwise falls back to the in-memory
    implementation.
    """

    global _freshdesk_instance

    if _freshdesk_instance is None:

        api_key = (
            settings.freshdesk_api_key or ""
        ).strip()

        domain = (
            settings.freshdesk_domain or ""
        ).strip()

        has_creds = (
            bool(api_key)
            and "TODO" not in api_key.upper()
        )

        has_domain = (
            bool(domain)
            and "TODO" not in domain.upper()
        )

        if has_creds and has_domain:

            logger.info(
                "freshdesk_client.initializing_real_client",
                domain=domain,
            )

            _freshdesk_instance = FreshdeskClient(
                api_key=api_key,
                domain=domain,
            )

        else:

            logger.warning(
                "freshdesk_client.using_in_memory_fallback",
                has_api_key=bool(api_key),
                has_domain=bool(domain),
            )

            _freshdesk_instance = (
                InMemoryFreshdeskClient()
            )

    return _freshdesk_instance