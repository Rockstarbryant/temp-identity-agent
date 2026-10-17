"""
Schemas for the structured page-inspection layer.

The AI agent reasons over PageSnapshot/PageElement objects — never raw
HTML — per the architecture's requirement that pages aren't dumped
wholesale into the LLM.
"""
from pydantic import BaseModel


class PageElement(BaseModel):
    """One interactive element found on the page."""

    element_id: str  # stable id assigned during inspection (data-tia-id attribute)
    tag: str  # "input" | "select" | "textarea" | "button" | "a" | etc.
    type: str = ""  # input type ("email", "password", "checkbox", ...) if applicable
    name: str = ""
    label: str = ""
    placeholder: str = ""
    href: str = ""  # for links
    value: str = ""  # current value, if any (e.g. pre-filled input)
    visible: bool = True
    options: list[str] = []  # for <select> elements
    group: str = ""  # the question this control belongs to (radios, checkboxes, form-builder fields)
    checked: bool | None = None  # radios / checkboxes / switches
    required: bool = False


class PageSnapshot(BaseModel):
    """The full structured inspection result for one page."""

    url: str
    title: str = ""
    elements: list[PageElement] = []


class BrowserActionResult(BaseModel):
    """Generic result returned by every browser.* tool action."""

    success: bool
    message: str = ""
    snapshot: PageSnapshot | None = None
    screenshot_path: str = ""
