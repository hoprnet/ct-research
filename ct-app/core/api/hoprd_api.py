import logging
from typing import Any, Callable, Literal, Optional, TypeVar, Union, overload

from api_lib import ApiLib
from api_lib.method import Method
from api_lib.objects import RequestData, Response

from . import request_objects as req
from . import response_objects as resp

logger = logging.getLogger(__name__)


class HoprdAPI(ApiLib):
    """
    HOPRd API helper to handle exceptions and logging.
    """

    _TResponse = TypeVar("_TResponse", bound=Response)
    _TModel = TypeVar("_TModel")

    @overload
    async def try_req(
        self,
        method: Method,
        path: str,
        resp_type: None = None,
        data: Optional[RequestData] = None,
        use_api_prefix: bool = True,
        return_state: Literal[False] = False,
        timeout: int = 90,
    ) -> Optional[dict[str, Any]]: ...

    @overload
    async def try_req(
        self,
        method: Method,
        path: str,
        resp_type: type[_TResponse],
        data: Optional[RequestData] = None,
        use_api_prefix: bool = True,
        return_state: Literal[False] = False,
        timeout: int = 90,
    ) -> Optional[_TResponse]: ...

    @overload
    async def try_req(
        self,
        method: Method,
        path: str,
        resp_type: type[list[_TResponse]],
        data: Optional[RequestData] = None,
        use_api_prefix: bool = True,
        return_state: Literal[False] = False,
        timeout: int = 90,
    ) -> Optional[list[_TResponse]]: ...

    @overload
    async def try_req(
        self,
        method: Method,
        path: str,
        resp_type: type[_TModel],
        data: Optional[RequestData] = None,
        use_api_prefix: bool = True,
        return_state: Literal[False] = False,
        timeout: int = 90,
    ) -> Optional[_TModel]: ...

    @overload
    async def try_req(
        self,
        method: Method,
        path: str,
        resp_type: Optional[Callable] = None,
        data: Optional[RequestData] = None,
        use_api_prefix: bool = True,
        *,
        return_state: Literal[True] = True,
        timeout: int = 90,
    ) -> Optional[bool]: ...

    @overload
    async def try_req(
        self,
        method: Method,
        path: str,
        resp_type: Optional[Callable] = None,
        data: Optional[RequestData] = None,
        use_api_prefix: bool = True,
        return_state: bool = False,
        timeout: int = 90,
    ) -> Optional[Union[Response, dict]]: ...

    async def try_req(
        self,
        method: Method,
        path: str,
        resp_type: Optional[Callable] = None,
        data: Optional[RequestData] = None,
        use_api_prefix: bool = True,
        return_state: bool = False,
        timeout: int = 90,
    ) -> Optional[Union[Response, dict]]:
        # Delegate to ApiLib while preserving typed overloads for call sites.
        return await super().try_req(
            method,
            path,
            resp_type=resp_type,
            data=data,
            use_api_prefix=use_api_prefix,
            return_state=return_state,
            timeout=timeout,
        )

    async def _call_api_with_timeout(
        self,
        method: Method,
        path: str,
        data: Optional[RequestData] = None,
        timeout: int = 90,
        use_api_prefix: bool = True,
    ) -> tuple[Optional[int], Optional[object]]:
        status, body = await super()._call_api_with_timeout(
            method, path, data, timeout=timeout, use_api_prefix=use_api_prefix
        )
        # The base client turns any non-2xx answer into `None` and drops hoprd's error body
        # (e.g. `{"status": "INVALID_INPUT", "error": ...}`); log it so failures are diagnosable.
        if status is not None and status // 100 != 2:
            logger.warning(
                "hoprd API returned an error",
                {
                    "method": method.value,
                    "path": path,
                    "status": status,
                    "body": str(body)[:500],
                },
            )
        return status, body

    async def balances(self) -> Optional[resp.Balances]:
        """
        Returns the balance of the node.
        :return: balances: Balances | undefined
        """
        return await self.try_req(Method.GET, "/account/balances", resp.Balances)

    async def peers(
        self,
    ) -> list[resp.ConnectedPeer]:
        """
        Returns a list of peers.
        :param: status: str = "connected"
        :return: peers: list
        """
        if data := await self.try_req(Method.GET, "/network/connected", list[resp.ConnectedPeer]):
            return data
        else:
            return []

    async def address(self) -> Optional[resp.Addresses]:
        """
        Returns the address of the node.
        :return: address: Addresses | undefined
        """
        return await self.try_req(Method.GET, "/account/addresses", resp.Addresses)

    async def configuration(self) -> Optional[dict[str, Any]]:
        """
        Returns the runtime configuration of the node.
        :return: configuration: dict | undefined
        """
        return await self.try_req(Method.GET, "/node/configuration")

    async def list_udp_sessions(self) -> Optional[list[resp.Session]]:
        """
        Lists existing Session listeners over UDP
        :return: list[Session]
        """
        return await self.try_req(Method.GET, "/session/udp", list[resp.Session])

    async def post_udp_session(
        self,
        destination: str,
        relayer: str,
        listen_host: str = ":0",
    ) -> Union[resp.Session, resp.SessionFailure]:
        """
        Creates a new session returning the session listening host & port over UDP.
        :param: destination: Address of the recipient
        :param: relayer: Address of the relayer
        :param: listen_host: str
        :return: Session
        """
        capabilities_body = req.SessionCapabilitiesBody()
        target_body = req.SessionTargetBody()
        path_body = req.SessionPathBodyRelayers([relayer])

        data = req.CreateSessionBody(
            capabilities_body.as_array,
            destination,
            target_body.as_dict,
            listen_host,
            path_body.as_dict["relayers"],
            path_body.as_dict["relayers"],
            "0 KB",
        )

        try:
            r = await self.try_req(
                Method.POST,
                "/session/udp/explicit-path",
                resp.Session,
                data=data,
                timeout=4,
            )
            logger.debug(
                "API response for session creation", {"response": r.as_dict if r else None}
            )
            if r:
                return r
            else:
                # API call returned None - could be timeout, network error, or API error
                logger.error(
                    "API call returned None for session open",
                    {
                        "destination": destination,
                        "relayer": relayer,
                    },
                )
                return resp.SessionFailure(
                    {
                        "error": "api call returned none (timeout or connection error)",
                        "status": "NO_SESSION_OPENED",
                        "destination": destination,
                        "relayer": relayer,
                    }
                )
        except Exception as e:
            # Capture any exception details for better diagnostics
            error_type = type(e).__name__
            error_msg = str(e)
            return resp.SessionFailure(
                {
                    "error": f"{error_type}: {error_msg}",
                    "status": "NO_SESSION_OPENED",
                    "destination": destination,
                    "relayer": relayer,
                }
            )

    async def close_session(self, session: resp.Session) -> bool:
        """
        Closes an existing Session listener for the given IP protocol, IP and port.
        :param: session: Session
        """
        return bool(
            await self.try_req(Method.DELETE, session.as_path, return_state=True, timeout=1)
        )

    async def healthyz(self, timeout: int = 20) -> bool:
        """
        Checks if the node is healthy. Return True if `healthyz` returns 200 before timeout.
        """
        return await self.timeout_check_success("/healthyz", timeout=timeout)
