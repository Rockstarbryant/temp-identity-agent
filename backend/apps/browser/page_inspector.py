"""
Page inspection layer.

Runs a single JS scan inside the page (via Page.evaluate) that finds
every interactive element, tags each with a stable `data-tia-id`
attribute (so later actions — click/type/select — can address the
exact same element the agent reasoned about), and returns a plain
JSON-serializable list. That list is parsed into PageSnapshot here on
the Python side.

Screenshots are captured alongside inspection for the audit trail /
human review during HUMAN_ACTION_REQUIRED, but the structured element
list — not the screenshot — is what the agent reasons over. See
architecture.md section 7.
"""
from apps.browser.schemas import PageElement, PageSnapshot

# Runs inside the browser page. Selects the interactive-element universe
# the agent is allowed to act on, assigns a stable id, and extracts a
# best-effort human-readable label for each (explicit <label for>,
# aria-label, placeholder, then nearest visible text as a fallback).
_INSPECT_JS = """
() => {
    const SELECTOR = 'input:not([type="hidden"]), select, textarea, button, a[href], [role="button"]';
    const elements = Array.from(document.querySelectorAll(SELECTOR));
    let counter = 0;

    function ownLabelText(labelEl) {
        // Strip out any nested form control's own text/value before reading
        // the label's text, so e.g. <label>Country <select>...</select></label>
        // yields "Country", not "Country United States Canada".
        const clone = labelEl.cloneNode(true);
        clone.querySelectorAll('input, select, textarea, button').forEach((n) => n.remove());
        return (clone.innerText || clone.textContent || '').trim();
    }

    function labelFor(el) {
        if (el.id) {
            const explicit = document.querySelector(`label[for="${el.id}"]`);
            if (explicit) {
                const text = ownLabelText(explicit);
                if (text) return text;
            }
        }
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) return ariaLabel.trim();
        const parentLabel = el.closest('label');
        if (parentLabel) {
            const text = ownLabelText(parentLabel);
            if (text) return text;
        }
        if (el.placeholder) return el.placeholder.trim();
        const ownText = el.innerText?.trim() || el.textContent?.trim();
        if (ownText) return ownText.slice(0, 200);
        return '';
    }

    function isVisible(el) {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    }

    return elements.map((el) => {
        if (!el.hasAttribute('data-tia-id')) {
            el.setAttribute('data-tia-id', `tia-${counter++}-${Math.random().toString(36).slice(2, 8)}`);
        }
        const options = el.tagName === 'SELECT'
            ? Array.from(el.options).map((o) => o.value || o.text)
            : [];

        return {
            element_id: el.getAttribute('data-tia-id'),
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type') || '',
            name: el.getAttribute('name') || '',
            label: labelFor(el),
            placeholder: el.getAttribute('placeholder') || '',
            href: el.getAttribute('href') || '',
            value: el.value !== undefined ? String(el.value) : '',
            visible: isVisible(el),
            options: options,
        };
    });
}
"""


def inspect_page(page) -> PageSnapshot:
    """
    Run the structured inspection scan on a live Playwright Page and
    return a PageSnapshot. `page` is a playwright.sync_api.Page.
    """
    raw_elements = page.evaluate(_INSPECT_JS)
    elements = [PageElement(**el) for el in raw_elements]
    return PageSnapshot(url=page.url, title=page.title(), elements=elements)
