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
    process_message: bool
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


class UnsubscribeParams(ProtocolModel):
    topic: str


class UnsubscribeResult(ProtocolModel):
    success: bool


class SendMessageParams(ProtocolModel):
    topic: str
    payload: dict[str, JsonValue]


class SendMessageResult(ProtocolModel):
    accepted: bool
    message_id: str
    delivered_to: int


class ProcessMessageParams(ProtocolModel):
    topic: str
    payload: dict[str, JsonValue]


class ProcessMessageResult(ProtocolModel):
    processed: bool
    status: str
    message: str


class PingParams(ProtocolModel):
    pass


class PingResult(ProtocolModel):
    timestamp: str


class AgentBusServerCallbacks(Protocol):
    """Callbacks for server request handlers."""

    async def handle_initialize(self, params: InitializeParams) -> InitializeResult: ...
    async def handle_subscribe(self, params: SubscribeParams) -> SubscribeResult: ...
    async def handle_unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult: ...
    async def handle_ping(self, params: PingParams) -> PingResult: ...
    async def send_message(self, params: SendMessageParams) -> SendMessageResult: ...


def register_server_callbacks(framework: JSONRPCFramework, callbacks: AgentBusServerCallbacks) -> None:
    """Register server callbacks."""

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

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult: ...


def register_client_callbacks(framework: JSONRPCFramework, callbacks: AgentBusClientCallbacks) -> None:
    """Register client callbacks.

    Client-side: registers handlers for requests from the server.
    """

    async def _process_message(params: dict[str, object]) -> dict[str, object]:
        params_model = ProcessMessageParams.model_validate(params)
        result_model = await callbacks.process_message(params_model)
        return result_model.model_dump(by_alias=True)

    framework.register_method("processMessage", _process_message)


class AgentBusServerApi:
    """Server API for bus->peer requests."""

    def __init__(self, framework: JSONRPCFramework) -> None:
        self._framework = framework

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Send processMessage request from bus to a peer."""
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("processMessage", params_dict)
        return ProcessMessageResult.model_validate(result_dict)


class AgentBusClientApi:
    """Client API for peer->bus requests."""

    def __init__(self, framework: JSONRPCFramework) -> None:
        self._framework = framework

    async def initialize(self, params: InitializeParams) -> InitializeResult:
        """Send initialize request to server."""
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("initialize", params_dict)
        return InitializeResult.model_validate(result_dict)

    async def subscribe(self, params: SubscribeParams) -> SubscribeResult:
        """Send subscribe request to server."""
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("subscribe", params_dict)
        return SubscribeResult.model_validate(result_dict)

    async def unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult:
        """Send unsubscribe request to server."""
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("unsubscribe", params_dict)
        return UnsubscribeResult.model_validate(result_dict)

    async def send_message(self, params: SendMessageParams) -> SendMessageResult:
        """Send message request to server."""
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("sendMessage", params_dict)
        return SendMessageResult.model_validate(result_dict)

    async def ping(self, params: PingParams) -> PingResult:
        """Send ping request to server."""
        params_dict = params.model_dump(by_alias=True)
        result_dict = await self._framework.send_request("ping", params_dict)
        return PingResult.model_validate(result_dict)


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
    "ProcessMessageParams",
    "ProcessMessageResult",
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
