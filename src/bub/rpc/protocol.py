"""Agent Bus specific protocol types and API methods."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from bub.rpc.framework import JSONRPCFramework

JsonValue = object


class ProtocolModel(BaseModel):
    """Base model for Agent Bus protocol types.

    Uses alias_generator to convert snake_case to camelCase.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
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
    success: bool
    subscription_id: str = "sub_unknown"


class UnsubscribeParams(ProtocolModel):
    topic: str


class UnsubscribeResult(ProtocolModel):
    success: bool


class SendMessageParams(ProtocolModel):
    topic: str
    payload: dict[str, JsonValue]


class SendMessageResult(ProtocolModel):
    success: bool
    stop_propagation: bool = False


class PingParams(ProtocolModel):
    pass


class PingResult(ProtocolModel):
    timestamp: str


class PublishInboundParams(ProtocolModel):
    channel: str
    sender_id: str
    chat_id: str
    content: str


class PublishInboundResult(ProtocolModel):
    success: bool


class PublishOutboundParams(ProtocolModel):
    channel: str
    chat_id: str
    content: str


class PublishOutboundResult(ProtocolModel):
    success: bool


class AgentBusServerCallbacks(Protocol):
    """Callbacks for server to call on client."""

    async def handle_initialize(self, params: InitializeParams) -> InitializeResult: ...
    async def handle_subscribe(self, params: SubscribeParams) -> SubscribeResult: ...
    async def handle_unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult: ...
    async def handle_ping(self, params: PingParams) -> PingResult: ...
    async def send_message(self, params: SendMessageParams) -> SendMessageResult: ...


def register_server_callbacks(framework: JSONRPCFramework, callbacks: AgentBusServerCallbacks) -> None:
    """Register server callbacks.

    Server-side: registers callbacks that the server can call on the client.
    """

    async def _handle_initialize(params: dict[str, object]) -> dict[str, object]:
        params_model = InitializeParams.model_validate(params)
        result_model = await callbacks.handle_initialize(params_model)
        return result_model.model_dump(by_alias=True)

    async def _handle_subscribe(params: dict[str, object]) -> dict[str, object]:
        params_model = SubscribeParams.model_validate(params)
        result_model = await callbacks.handle_subscribe(params_model)
        return result_model.model_dump(by_alias=True)

    async def _handle_unsubscribe(params: dict[str, object]) -> dict[str, object]:
        params_model = UnsubscribeParams.model_validate(params)
        result_model = await callbacks.handle_unsubscribe(params_model)
        return result_model.model_dump(by_alias=True)

    async def _send_message(params: dict[str, object]) -> dict[str, object]:
        params_model = SendMessageParams.model_validate(params)
        result_model = await callbacks.send_message(params_model)
        return result_model.model_dump(by_alias=True)

    async def _handle_ping(params: dict[str, object]) -> dict[str, object]:
        params_model = PingParams.model_validate(params)
        result_model = await callbacks.handle_ping(params_model)
        return result_model.model_dump(by_alias=True)

    framework.register_method("initialize", _handle_initialize)
    framework.register_method("subscribe", _handle_subscribe)
    framework.register_method("unsubscribe", _handle_unsubscribe)
    framework.register_method("ping", _handle_ping)
    framework.register_method("sendMessage", _send_message)


class AgentBusClientCallbacks(Protocol):
    """Callbacks for client to handle server requests."""

    async def send_message(self, params: SendMessageParams) -> SendMessageResult: ...


def register_client_callbacks(framework: JSONRPCFramework, callbacks: AgentBusClientCallbacks) -> None:
    """Register client callbacks.

    Client-side: registers handlers for requests from the server.
    """

    async def _send_message(params: dict[str, object]) -> dict[str, object]:
        params_model = SendMessageParams.model_validate(params)
        result_model = await callbacks.send_message(params_model)
        return result_model.model_dump(by_alias=True)

    framework.register_method("sendMessage", _send_message)


class AgentBusServerApi:
    """Agent Bus protocol API.

    Provides typed methods for Agent Bus operations.
    """

    def __init__(self, framework: JSONRPCFramework) -> None:
        self._framework = framework

    async def send_message(self, params: SendMessageParams) -> SendMessageResult:
        """Send message request.

        Server-side: sends message request to client.
        Returns SendMessageResult with stop_propagation flag.
        """
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("sendMessage", params_dict)
        return SendMessageResult.model_validate(result_dict)

    async def ping(self, params: PingParams) -> PingResult:
        """Send ping request.

        Client-side: sends ping request to server.
        Returns timestamp.
        """
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("ping", params_dict)
        return PingResult.model_validate(result_dict)


class AgentBusClientApi:
    """Client API for handling server notifications."""

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

    async def send_message(self, params: SendMessageParams) -> SendMessageResult:
        """Send message request.

        Client-side: sends message to server for broadcasting to subscribers.
        """
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("sendMessage", params_dict)
        return SendMessageResult.model_validate(result_dict)


__all__ = [
    "AgentBusClientApi",
    "AgentBusClientCallbacks",
    "AgentBusServerApi",
    "AgentBusServerCallbacks",
    "ClientInfo",
    "InitializeParams",
    "InitializeResult",
    "JsonValue",
    "PingParams",
    "PingResult",
    "ProtocolModel",
    "SendMessageParams",
    "SendMessageResult",
    "ServerCapabilities",
    "ServerInfo",
    "SubscribeParams",
    "SubscribeResult",
    "UnsubscribeParams",
    "UnsubscribeResult",
    "register_client_callbacks",
    "register_server_callbacks",
]
