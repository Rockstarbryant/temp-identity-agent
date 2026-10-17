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
    const SELECTOR = 'input:not([type="hidden"]), select, textarea, button, a[href], [role="button"], ' +
        '[role="radio"], [role="checkbox"], [role="option"], [role="combobox"], [role="listbox"], [role="textbox"], [role="switch"]';
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
        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const text = labelledBy.split(/\\s+/)
                .map((id) => { const n = document.getElementById(id); return n ? n.innerText.trim() : ''; })
                .filter(Boolean).join(' ');
            if (text) return text.slice(0, 200);
        }
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

    function groupFor(el) {
        // The question this control answers: a fieldset legend, or the heading of its
        // list item / form group (Google Forms and most custom form builders).
        const fieldset = el.closest('fieldset');
        const legend = fieldset && fieldset.querySelector('legend');
        if (legend && legend.innerText.trim()) return legend.innerText.trim().slice(0, 200);
        let node = el.parentElement;
        for (let depth = 0; node && depth < 8; depth++, node = node.parentElement) {
            if (!node.matches('[role="listitem"], [role="group"], [role="radiogroup"], .form-group')) continue;
            const heading = node.querySelector('[role="heading"], legend, label, h1, h2, h3, h4');
            if (heading && heading.innerText.trim()) return heading.innerText.trim().slice(0, 200);
            if (node.getAttribute('role') === 'listitem') {
                // Form builders put the question text first in the list item.
                const first = (node.innerText || '').split('\\n').map((t) => t.trim()).find(Boolean);
                if (first) return first.slice(0, 200);
            }
        }
        return '';
    }

    function checkedState(el) {
        const aria = el.getAttribute('aria-checked');
        if (aria === 'true') return true;
        if (aria === 'false') return false;
        if (el.type === 'checkbox' || el.type === 'radio') return !!el.checked;
        return null;
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
            type: el.getAttribute('type') || el.getAttribute('role') || '',
            name: el.getAttribute('name') || '',
            label: labelFor(el),
            placeholder: el.getAttribute('placeholder') || '',
            href: el.getAttribute('href') || '',
            value: el.value !== undefined ? String(el.value) : '',
            visible: isVisible(el),
            options: options,
            group: groupFor(el),
            checked: checkedState(el),
            required: el.required === true || el.getAttribute('aria-required') === 'true',
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
