"""
Random display name and username generation for temporary identities.

Selection uses `secrets.choice`, the same CSPRNG used for password
generation — these values end up in account records, so they should
not be predictable from a seeded/observable RNG.
"""
import secrets

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn",
    "Rowan", "Sage", "Drew", "Emerson", "Finley", "Harper", "Hayden", "Jamie",
    "Kendall", "Logan", "Marlowe", "Parker", "Reese", "Skyler", "Tatum",
    "Blake", "Cameron", "Dakota", "Elliot", "Frankie", "Gray", "Hunter",
    "Indigo", "Jules", "Kai", "Lane", "Micah", "Nico", "Oakley", "Peyton",
]

LAST_NAMES = [
    "Bennett", "Carter", "Diaz", "Ellis", "Foster", "Grant", "Hayes", "Irwin",
    "Jensen", "Kramer", "Lambert", "Mercer", "Nolan", "Ortiz", "Pierce",
    "Quintero", "Reyes", "Sawyer", "Turner", "Underwood", "Vance", "Walsh",
    "Xu", "Young", "Zimmer", "Abbott", "Beckett", "Cross", "Dunbar", "Emmerich",
]


def generate_display_name() -> str:
    """A plausible, non-identifying random full name (not a real person)."""
    return f"{secrets.choice(FIRST_NAMES)} {secrets.choice(LAST_NAMES)}"


def generate_username(max_suffix_digits: int = 4) -> str:
    """
    A lowercase, letters-and-digits username: first name + last name + a few random digits,
    e.g. 'jordanmercer4821'. (No dots or dashes: many sites reject them.) Digit count is configurable so callers can
    tune collision probability for high-volume usage.
    """
    first = secrets.choice(FIRST_NAMES).lower()
    last = secrets.choice(LAST_NAMES).lower()
    suffix = "".join(str(secrets.randbelow(10)) for _ in range(max_suffix_digits))
    return f"{first}{last}{suffix}"
