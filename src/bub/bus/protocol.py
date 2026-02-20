"""Agent Bus specific protocol types and API methods."""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
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
    """Client information provided during initialization."""

    name: str
    version: str


class ServerInfo(ProtocolModel):
    """Server information returned during initialization."""

    name: str
    version: str


class ServerCapabilities(ProtocolModel):
    """Server capabilities advertised during initialization."""

    subscribe: bool
    process_message: bool
    addresses: list[str]


class InitializeParams(ProtocolModel):
    """Parameters for the initialize method."""

    client_id: str
    client_info: ClientInfo | None = None


class InitializeResult(ProtocolModel):
    """Result returned from the initialize method."""

    server_id: str
    server_info: ServerInfo
    capabilities: ServerCapabilities


class SubscribeParams(ProtocolModel):
    """Parameters for the subscribe method."""

    address: str


class SubscribeResult(ProtocolModel):
    """Result returned from the subscribe method."""

    success: bool


class UnsubscribeParams(ProtocolModel):
    """Parameters for the unsubscribe method."""

    address: str


class UnsubscribeResult(ProtocolModel):
    """Result returned from the unsubscribe method."""

    success: bool


class SendMessageParams(ProtocolModel):
    """Parameters for the sendMessage method."""

    from_: str = Field(alias="from")  # JSON field: 'from', Python attribute: 'from_'
    to: str
    message_id: str
    payload: dict[str, JsonValue]


class SendMessageResult(ProtocolModel):
    """Result from sendMessage - aggregates all individual delivery results.

    Since sendMessage fans out to multiple subscribers, this contains the array
    of stripped MessageAck responses from each recipient.
    Use len(acks) to get delivery count.

    Note: Retry fields (shouldRetry, retrySeconds) are excluded from acks
    since retry is handled by the bus server internally.
    """

    accepted: bool
    message_id: str
    acks: list[MessageAck]  # Stripped results from each recipient


class ProcessMessageParams(ProtocolModel):
    """Parameters for the processMessage method.

    Note: The JSON field is 'from' (reserved word in Python), so the Python
    attribute is 'from_' with an alias to map it correctly.
    """

    from_: str = Field(alias="from")  # JSON field: 'from', Python attribute: 'from_'
    to: str
    message_id: str
    payload: dict[str, JsonValue]


class ProcessMessageResult(ProtocolModel):
    """Result from a single processMessage call to one peer.

    Includes retry fields for bus server retry decisions.
    """

    success: bool
    message: str
    should_retry: bool
    retry_seconds: int
    payload: dict[str, JsonValue]  # Response payload from the peer


class MessageAck(ProtocolModel):
    """Stripped result for sendMessage.acks.

    Excludes retry fields since retry is handled by the bus server internally.
    """

    success: bool
    message: str
    payload: dict[str, JsonValue]  # Response payload from the peer


class PingParams(ProtocolModel):
    """Parameters for the ping method."""

    pass


class PingResult(ProtocolModel):
    """Result returned from the ping method."""

    timestamp: str


class ConnectionInfo(ProtocolModel):
    """Information about a connected client."""

    client_id: str
    connection_id: str
    subscriptions: list[str]
    client_info: ClientInfo | None = None


class GetStatusParams(ProtocolModel):
    """Parameters for the getStatus method."""

    pass


class GetStatusResult(ProtocolModel):
    """Result returned from the getStatus method."""

    server_id: str
    connections: list[ConnectionInfo]


class AgentBusServerCallbacks(Protocol):
    """Callbacks for server request handlers."""

    async def handle_initialize(self, params: InitializeParams) -> InitializeResult: ...
    async def handle_subscribe(self, params: SubscribeParams) -> SubscribeResult: ...
    async def handle_unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult: ...
    async def handle_ping(self, params: PingParams) -> PingResult: ...
    async def handle_get_status(self, params: GetStatusParams) -> GetStatusResult: ...
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

    async def _handle_get_status(params: dict[str, object]) -> dict[str, object]:
        params_model = GetStatusParams.model_validate(params)
        result_model = await callbacks.handle_get_status(params_model)
        return result_model.model_dump(by_alias=True)

    framework.register_method("initialize", _handle_initialize)
    framework.register_method("subscribe", _handle_subscribe)
    framework.register_method("unsubscribe", _handle_unsubscribe)
    framework.register_method("ping", _handle_ping)
    framework.register_method("getStatus", _handle_get_status)
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

    def __init__(self, framework: JSONRPCFramework, client_id: str | None = None) -> None:
        self._framework = framework
        self._client_id = client_id or f"api-{id(self):x}"
        self._message_counter = 0

    def _next_message_id(self) -> str:
        """Generate next sequential message ID atomically."""
        self._message_counter += 1
        return f"msg_{self._client_id}_{self._message_counter:010d}"

    async def send_message2(
        self,
        from_: str,
        to: str,
        payload: dict[str, JsonValue],
    ) -> SendMessageResult:
        """Send message with auto-generated message ID.

        This is a convenience method that manages message_id generation
        at the API instance level with atomic increment.
        """
        message_id = self._next_message_id()
        params = SendMessageParams(from_=from_, to=to, message_id=message_id, payload=payload)  # type: ignore[call-arg]
        return await self.send_message(params)

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
    "ConnectionInfo",
    "GetStatusParams",
    "GetStatusResult",
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
