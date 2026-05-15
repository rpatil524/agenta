"""Structured rendering helpers for prompt messages and JSON-like objects.

This module sits one layer above ``render_template``. It knows where strings
can appear inside prompt messages and response-format structures, but it has no
runtime, provider, secret, or handler knowledge.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence, Union

from pydantic import BaseModel

from agenta.sdk.utils.templating import TemplateMode, render_template

if TYPE_CHECKING:
    from agenta.sdk.utils.types import Message


MessageInput = Union["Message", Mapping[str, Any]]


class StructuredRenderingError(ValueError):
    """Raised when structured message or JSON-like rendering fails.

    ``path`` is a logical data location, not a filesystem path. It points to the
    field that failed to render, such as ``messages[0].content`` or
    ``json_schema.schema.properties.score.description``. Callers use this to
    wrap errors with service-specific exception types while keeping failures
    easy to debug and assert in tests.
    """

    def __init__(
        self,
        *,
        path: str,
        message: str,
        original_error: Optional[BaseException] = None,
        template: Optional[str] = None,
    ) -> None:
        self.path = path
        self.message = message
        self.original_error = original_error
        self.template = template
        super().__init__(f"{path}: {message}")


def _render_string(
    *,
    value: str,
    mode: TemplateMode,
    context: Mapping[str, Any],
    path: str,
) -> str:
    """Render one string and attach its logical location to any failure."""

    try:
        return render_template(template=value, mode=mode, context=context)
    except Exception as exc:
        raise StructuredRenderingError(
            path=path,
            message=str(exc),
            original_error=exc,
            template=value,
        ) from exc


def _part_type(part: Any) -> Optional[str]:
    if isinstance(part, Mapping):
        part_type = part.get("type")
        return part_type if isinstance(part_type, str) else None
    return getattr(part, "type", None)


def _part_text(part: Any) -> Any:
    if isinstance(part, Mapping):
        return part.get("text")
    return getattr(part, "text", None)


def _copy_part_with_text(part: Any, text: str) -> Any:
    """Return a copy of a text content part with rendered text.

    Content parts may arrive as plain dicts or Pydantic models. Preserve the
    original shape so callers do not need to normalize messages before passing
    them to the provider.
    """

    if isinstance(part, Mapping):
        new_part = deepcopy(dict(part))
        new_part["text"] = text
        return new_part
    if isinstance(part, BaseModel):
        return part.model_copy(update={"text": text}, deep=True)
    new_part = deepcopy(part)
    setattr(new_part, "text", text)
    return new_part


def _is_message_model(message: Any) -> bool:
    """Detect Agenta-style message models without importing ``Message``.

    ``types.py`` imports this module at runtime. Importing ``Message`` here would
    create a circular import, so we validate the small structural contract this
    renderer needs instead.
    """

    return (
        isinstance(message, BaseModel)
        and hasattr(message, "model_copy")
        and hasattr(message, "role")
        and hasattr(message, "content")
    )


def _render_content_part(
    *,
    part: Any,
    mode: TemplateMode,
    context: Mapping[str, Any],
    message_index: int,
    part_index: int,
) -> Any:
    path = f"messages[{message_index}].content[{part_index}]"
    part_type = _part_type(part)

    if part_type is None:
        raise StructuredRenderingError(
            path=path,
            message="content part must include a string 'type' field",
        )

    if part_type == "text":
        text = _part_text(part)
        if not isinstance(text, str):
            raise StructuredRenderingError(
                path=path,
                message="text content part must include a string 'text' field",
            )
        rendered_text = _render_string(
            value=text,
            mode=mode,
            context=context,
            path=f"{path}.text",
        )
        return _copy_part_with_text(part, rendered_text)

    if part_type in {"image_url", "file"}:
        # Non-text parts are provider payloads, not templates. Rendering nested
        # strings inside them could corrupt image URLs, file IDs, or base64 data.
        return deepcopy(part)

    raise StructuredRenderingError(
        path=path,
        message=f"unsupported content part type: {part_type}",
    )


def _render_message_content(
    *,
    content: Any,
    mode: TemplateMode,
    context: Mapping[str, Any],
    message_index: int,
) -> Any:
    path = f"messages[{message_index}].content"

    if content is None:
        return None

    if isinstance(content, str):
        return _render_string(
            value=content,
            mode=mode,
            context=context,
            path=path,
        )

    if isinstance(content, list):
        return [
            _render_content_part(
                part=part,
                mode=mode,
                context=context,
                message_index=message_index,
                part_index=part_index,
            )
            for part_index, part in enumerate(content)
        ]

    raise StructuredRenderingError(
        path=path,
        message="content must be None, a string, or a list of known content parts",
    )


def _render_message(
    *,
    message: MessageInput,
    mode: TemplateMode,
    context: Mapping[str, Any],
    message_index: int,
) -> MessageInput:
    path = f"messages[{message_index}]"

    if _is_message_model(message):
        role = getattr(message, "role", None)
        if not isinstance(role, str):
            raise StructuredRenderingError(
                path=f"{path}.role",
                message="message role must be a string",
            )
        rendered_content = _render_message_content(
            content=message.content,
            mode=mode,
            context=context,
            message_index=message_index,
        )
        return message.model_copy(update={"content": rendered_content}, deep=True)

    if not isinstance(message, Mapping):
        raise StructuredRenderingError(
            path=path,
            message="message must be an Agenta Message object or mapping",
        )

    role = message.get("role")
    if not isinstance(role, str):
        raise StructuredRenderingError(
            path=f"{path}.role",
            message="message role must be a string",
        )

    rendered = deepcopy(dict(message))
    rendered["content"] = _render_message_content(
        content=message.get("content"),
        mode=mode,
        context=context,
        message_index=message_index,
    )
    return rendered


def render_messages(
    *,
    messages: Sequence[MessageInput],
    mode: TemplateMode,
    context: Mapping[str, Any],
) -> list[MessageInput]:
    """Render text-bearing fields inside prompt messages.

    Supports Agenta ``Message`` objects and dict-like messages. String content
    and text content parts are rendered. Known non-text parts are preserved.
    """

    if isinstance(messages, (str, bytes, Mapping)):
        raise StructuredRenderingError(
            path="messages",
            message="messages must be a sequence of Message objects or mappings",
        )
    try:
        message_list = list(messages)
    except TypeError as exc:
        raise StructuredRenderingError(
            path="messages",
            message="messages must be a sequence of Message objects or mappings",
        ) from exc

    return [
        _render_message(
            message=message,
            mode=mode,
            context=context,
            message_index=message_index,
        )
        for message_index, message in enumerate(message_list)
    ]


def render_json_like(
    *,
    value: Any,
    mode: TemplateMode,
    context: Mapping[str, Any],
    render_keys: bool = True,
    path: str = "value",
) -> Any:
    """Recursively render strings in a JSON-like structure.

    This is used for response-format objects such as chat/completion
    ``response_format`` and judge ``json_schema``. It renders string values and,
    by default, string keys. It does not validate JSON Schema correctness.
    """

    if isinstance(value, str):
        return _render_string(value=value, mode=mode, context=context, path=path)

    if isinstance(value, list):
        return [
            render_json_like(
                value=item,
                mode=mode,
                context=context,
                render_keys=render_keys,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]

    if isinstance(value, Mapping):
        rendered: dict[Any, Any] = {}
        for key, item in value.items():
            rendered_key = key
            if render_keys and isinstance(key, str):
                rendered_key = _render_string(
                    value=key,
                    mode=mode,
                    context=context,
                    path=f"{path}.<key:{key}>",
                )
            if rendered_key in rendered:
                raise StructuredRenderingError(
                    path=f"{path}.<key:{key}>",
                    message=f"rendered key collision for {rendered_key!r}",
                )
            rendered[rendered_key] = render_json_like(
                value=item,
                mode=mode,
                context=context,
                render_keys=render_keys,
                path=f"{path}.{rendered_key}",
            )
        return rendered

    return deepcopy(value)
