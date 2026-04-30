"""Unit tests for the low-level rendering helper.

Covers each substitution mode (`curly`, `fstring`, `jinja2`) and verifies the
behavior the call sites depend on:

- top-level / nested / array index lookups in `curly`;
- JSONPath (``$.a.b``) and JSON Pointer (``/a/b``) resolution;
- literal-key-first lookup (a top-level key literally named ``foo.bar``);
- whole-object insertion as compact JSON text;
- Python ``str.format`` semantics in ``fstring``;
- sandboxed Jinja2 rendering with ``TemplateError`` raised on sandbox violations.

It also pins the call-site behaviors that must not change in WP-B1:
``PromptTemplate._format_with_template`` and the handlers'
``_format_with_template`` continue to produce the same outputs they did before
the helper extraction for a representative template set.
"""

import pytest

from agenta.sdk.engines.running.handlers import _format_with_template
from agenta.sdk.types import PromptTemplate, TemplateFormatError
from agenta.sdk.utils.lazy import _load_jinja2
from agenta.sdk.utils.templating import render_template


# ---- curly mode ----------------------------------------------------------------


def test_curly_resolves_top_level_keys():
    out = render_template(
        template="hello {{name}}",
        mode="curly",
        context={"name": "Ada"},
    )
    assert out == "hello Ada"


def test_curly_resolves_nested_dot_notation():
    out = render_template(
        template="profile.name={{profile.name}}",
        mode="curly",
        context={"profile": {"name": "Ada"}},
    )
    assert out == "profile.name=Ada"


def test_curly_resolves_array_index():
    out = render_template(
        template="first={{tags.0}}",
        mode="curly",
        context={"tags": ["alpha", "beta"]},
    )
    assert out == "first=alpha"


def test_curly_resolves_json_path():
    out = render_template(
        template="name={{$.profile.name}}",
        mode="curly",
        context={"profile": {"name": "Ada"}},
    )
    assert out == "name=Ada"


def test_curly_resolves_json_pointer():
    out = render_template(
        template="name={{/profile/name}}",
        mode="curly",
        context={"profile": {"name": "Ada"}},
    )
    assert out == "name=Ada"


def test_curly_literal_key_wins_over_nested_traversal():
    """A top-level key named ``foo.bar`` is preferred over ``foo`` -> ``bar``."""

    out = render_template(
        template="value={{foo.bar}}",
        mode="curly",
        context={"foo.bar": "literal", "foo": {"bar": "nested"}},
    )
    assert out == "value=literal"


def test_curly_renders_whole_object_as_compact_json():
    out = render_template(
        template="profile={{profile}}",
        mode="curly",
        context={"profile": {"name": "Ada", "tags": ["x", "y"]}},
    )
    assert out == 'profile={"name": "Ada", "tags": ["x", "y"]}'


def test_curly_raises_on_unresolved_placeholder():
    with pytest.raises(ValueError, match="Template variables not found"):
        render_template(
            template="hello {{missing}}",
            mode="curly",
            context={},
        )


# ---- fstring mode --------------------------------------------------------------


def test_fstring_uses_str_format_semantics():
    out = render_template(
        template="hello {name}",
        mode="fstring",
        context={"name": "Ada"},
    )
    assert out == "hello Ada"


def test_fstring_raises_on_missing_key():
    with pytest.raises(KeyError):
        render_template(
            template="hello {missing}",
            mode="fstring",
            context={},
        )


# ---- jinja2 mode ---------------------------------------------------------------


def test_jinja2_renders_safe_template():
    out = render_template(
        template="hello {{ name }}",
        mode="jinja2",
        context={"name": "Ada"},
    )
    assert out == "hello Ada"


def test_jinja2_raises_template_error_on_sandbox_violation():
    _, TemplateError = _load_jinja2()
    payload = "{{ lipsum.__globals__['os'].popen('id').read() }}"

    with pytest.raises(TemplateError):
        render_template(
            template=payload,
            mode="jinja2",
            context={},
        )


# ---- unknown mode --------------------------------------------------------------


def test_unknown_mode_raises_value_error():
    with pytest.raises(ValueError, match="Unknown template format"):
        render_template(template="hi", mode="bogus", context={})


# ---- call-site behavior preservation ------------------------------------------


def test_handlers_format_with_template_curly_preserves_behavior():
    """Judge handler ``_format_with_template`` keeps its existing behavior."""

    out = _format_with_template(
        content="profile={{profile}} | name={{profile.name}}",
        format="curly",
        kwargs={"profile": {"name": "Ada"}},
    )
    assert out == 'profile={"name": "Ada"} | name=Ada'


def test_handlers_format_with_template_curly_raises_on_unresolved():
    with pytest.raises(ValueError):
        _format_with_template(
            content="hi {{missing}}",
            format="curly",
            kwargs={},
        )


def test_handlers_format_with_template_jinja2_silently_returns_on_sandbox_violation():
    """Judge keeps its silent-return-on-jinja-error behavior in WP-B1."""

    payload = "{{ lipsum.__globals__['os'].popen('id').read() }}"
    out = _format_with_template(content=payload, format="jinja2", kwargs={})
    assert out == payload


def test_prompt_template_curly_renders_with_helper():
    """Chat/completion ``PromptTemplate`` uses the helper transparently."""

    template = PromptTemplate(
        template_format="curly",
        messages=[
            {"role": "system", "content": "context={{profile}}"},
            {"role": "user", "content": "hi {{profile.name}}"},
        ],
    )

    formatted = template.format(profile={"name": "Ada"})

    assert formatted.messages[0].content == 'context={"name": "Ada"}'
    assert formatted.messages[1].content == "hi Ada"


def test_prompt_template_jinja2_raises_template_format_error_on_sandbox_violation():
    """Chat/completion keeps the raise-on-jinja-error behavior."""

    payload = "{{ lipsum.__globals__['os'].popen('id').read() }}"
    template = PromptTemplate(
        template_format="jinja2",
        messages=[{"role": "user", "content": payload}],
    )

    with pytest.raises(TemplateFormatError):
        template.format()


def test_prompt_template_curly_wraps_unresolved_as_template_format_error():
    template = PromptTemplate(
        template_format="curly",
        messages=[{"role": "user", "content": "hi {{missing}}"}],
    )
    with pytest.raises(TemplateFormatError) as exc_info:
        template.format()
    # Pin the legacy message text so chat/completion callers parsing the
    # exception keep working. The list-repr (``['missing']``) and trailing
    # period match the pre-WP-B1 wording.
    assert "Unreplaced variables in curly template: ['missing']." in str(exc_info.value)


def test_handlers_format_with_template_curly_unresolved_message_unchanged():
    """The judge's curly ValueError text is unchanged from pre-WP-B1."""

    from agenta.sdk.engines.running.handlers import _format_with_template

    with pytest.raises(ValueError) as exc_info:
        _format_with_template(content="hi {{missing}}", format="curly", kwargs={})
    assert "Template variables not found or unresolved: missing." in str(exc_info.value)


def test_prompt_template_fstring_missing_key_raises_template_format_error():
    template = PromptTemplate(
        template_format="fstring",
        messages=[{"role": "user", "content": "hi {missing}"}],
    )
    with pytest.raises(TemplateFormatError):
        template.format()
