"""Agent Bus specific protocol types and API methods."""

from pydantic import BaseModel, ConfigDict

from bub.rpc.protocol import JSONRPCFramework

JsonValue = object


class ProtocolModel(BaseModel):
    """Base model for Agent Bus protocol types.

    Uses alias_generator to convert snake_case to camelCase.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: (
            s.split("_")[0] + "".join(word.capitalize() for word in s.split("_")[1:]) if "_" in s else s
        ),
        extra="forbid",
    )


class ClientInfo(ProtocolModel):
    name: str
    version: str


class ServerInfo(ProtocolModel):
    name: str
    version: str


class ServerCapabilities(ProtocolModel):
    subscribe: bool
    publish: bool
    topics: list[str]


class InitializeParams(ProtocolModel):
    client_id: str
    client_info: ClientInfo | None = None


class InitializeResult(ProtocolModel):
    server_id: str
    server_info: ServerInfo
    capabilities: ServerCapabilities


class SubscribeParams(ProtocolModel):
    topic: str


class SubscribeResult(ProtocolModel):
    subscription_id: str


class UnsubscribeParams(ProtocolModel):
    subscription_id: str


class UnsubscribeResult(ProtocolModel):
    success: bool


class NotifyParams(ProtocolModel):
    topic: str
    payload: dict[str, JsonValue]


class PingParams(ProtocolModel):
    pass


class PingResult(ProtocolModel):
    timestamp: str


class AgentProtocol:
    """Agent Bus protocol API.

    Provides typed methods for Agent Bus operations.
    """

    def __init__(self, framework: JSONRPCFramework) -> None:
        self._framework = framework

    async def initialize(self, params: InitializeParams) -> InitializeResult:
        """Send initialize request.

        Client-side: sends initialization request to server.
        Returns server info and capabilities.
        """
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("initialize", params_dict)
        return InitializeResult.model_validate(result_dict)

    async def subscribe(self, params: SubscribeParams) -> SubscribeResult:
        """Send subscribe request.

        Client-side: sends subscribe request to server.
        Returns subscription ID.
        """
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("subscribe", params_dict)
        return SubscribeResult.model_validate(result_dict)

    async def unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult:
        """Send unsubscribe request.

        Client-side: sends unsubscribe request to server.
        """
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("unsubscribe", params_dict)
        return UnsubscribeResult.model_validate(result_dict)

    async def notify(self, params: NotifyParams) -> None:
        """Send notify notification.

        Client-side: sends notification to server (fire-and-forget).
        """
        params_dict = params.model_dump(by_alias=True)
        await self._framework.send_notification("notify", params_dict)

    async def ping(self, params: PingParams) -> PingResult:
        """Send ping request.

        Client-side: sends ping request to server.
        Returns timestamp.
        """
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("ping", params_dict)
        return PingResult.model_validate(result_dict)

    async def client_initialize(self, client_id: str, client_info: ClientInfo) -> InitializeResult:
        """Initialize connection (client-side).

        Sends initialize request to server.
        """
        params = InitializeParams(client_id=client_id, client_info=client_info)
        return await self.initialize(params)

    async def client_subscribe(self, topic: str) -> SubscribeResult:
        """Subscribe to topic (client-side).

        Sends subscribe request to server.
        """
        params = SubscribeParams(topic=topic)
        return await self.subscribe(params)

    async def client_unsubscribe(self, subscription_id: str) -> UnsubscribeResult:
        """Unsubscribe from topic (client-side).

        Sends unsubscribe request to server.
        """
        params = UnsubscribeParams(subscription_id=subscription_id)
        return await self.unsubscribe(params)

    async def client_notify(self, topic: str, payload: dict[str, JsonValue]) -> None:
        """Send notification (client-side).

        Sends notify notification to server.
        """
        params = NotifyParams(topic=topic, payload=payload)
        await self._framework.send_notification("notify", params.model_dump(by_alias=True))

    async def client_ping(self) -> PingResult:
        """Ping server (client-side).

        Sends ping request to server.
        """
        params = PingParams()
        return await self.ping(params)


__all__ = [
    "AgentProtocol",
    "ClientInfo",
    "InitializeParams",
    "InitializeResult",
    "JsonValue",
    "NotifyParams",
    "PingParams",
    "PingResult",
    "ProtocolModel",
    "ServerCapabilities",
    "ServerInfo",
    "SubscribeParams",
    "SubscribeResult",
    "UnsubscribeParams",
    "UnsubscribeResult",
]
