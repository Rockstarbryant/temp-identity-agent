/**
 * All homepage copy lives here so wording can be reviewed and changed without touching layout code.
 * Every capability below was checked against the repository (README, docs/security.md,
 * docs/email.md and the frontend/backend code) rather than assumed.
 */

export const DEFINITION =
  "Temp Identity Agent is a personal account-registration assistant that helps users register for supported websites using temporary or connected email, retrieve verification messages, generate unique passwords, and save login credentials in a vault.";

export const NAV_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#modes", label: "Account modes" },
  { href: "#faq", label: "FAQ" },
] as const;

export const PROBLEMS = [
  {
    icon: "inbox",
    title: "Your inbox gets crowded",
    text: "Signing up for websites you barely use can expose your primary email address to unwanted marketing and future phishing attempts.",
  },
  {
    icon: "form",
    title: "Forms take too much time",
    text: "Names, addresses, occupations, interests, and other fields can turn a simple signup into a frustrating chore.",
  },
  {
    icon: "key",
    title: "Passwords become a problem",
    text: "Remembering a different password for every account is difficult, so people often reuse passwords or struggle to recover forgotten accounts.",
  },
] as const;

export const STEPS = [
  { title: "Paste the link", text: "Give Temp Identity Agent the address of the page where you want an account." },
  { title: "Fill the registration form", text: "The agent reads the form and fills the fields it supports, using a temporary or connected email." },
  { title: "Retrieve the code or link", text: "When the site sends a verification code or link, the agent picks it up from the inbox and completes the step." },
  { title: "Get your credentials", text: "You receive the login details and they are saved in your vault, ready when you need them." },
] as const;

export const TEMPORARY_FEATURES = [
  "Obtain a temporary email through a supported provider.",
  "Generate disposable registration details for supported fields.",
  "Automatically fill supported forms.",
  "Retrieve verification messages when supported.",
  "Generate a unique password for the website.",
  "Save credentials in the vault for a configured period.",
  "Check the associated inbox inside the platform while it remains available.",
] as const;

export const PERMANENT_FEATURES = [
  "Switch to permanent account mode.",
  "Connect Gmail through the supported settings flow.",
  "Configure the required Google app password.",
  "Receive supported verification messages through the connected inbox.",
  "Generate a unique password for each registered website.",
  "Save credentials without the temporary-account expiry rule.",
] as const;

export const FALLBACK_STEPS = [
  "The agent examines the form and identifies supported fields.",
  "It prepares values such as the username, email, and password for copying.",
  "You complete the registration in the website's supported browser and retrieve verification messages through the associated inbox when available.",
] as const;

export const FAQ: { q: string; a: string }[] = [
  {
    q: "What is Temp Identity Agent?",
    a: "Temp Identity Agent is a personal account-registration assistant that helps users complete supported website registrations, retrieve verification messages, generate unique passwords, and save their login credentials.",
  },
  {
    q: "Does it use my main email address?",
    a: "Temporary mode uses a temporary email address obtained through a supported provider. Permanent mode uses the Gmail account you explicitly connect for supported registration workflows.",
  },
  {
    q: "What's the difference between temporary and permanent mode?",
    a: "Temporary mode is intended for accounts you may not need for long and uses configured expiry rules. Permanent mode uses your connected Gmail account and does not apply the temporary-account expiry rule to saved credentials.",
  },
  {
    q: "Does it work on every website?",
    a: "No. Websites differ in their registration forms, email policies, browser requirements, CAPTCHA challenges, and authentication methods. Some registrations cannot be automated.",
  },
  {
    q: "What happens when a website blocks automation?",
    a: "When supported, the agent can prepare registration values for manual entry. You complete the registration in the website's supported browser.",
  },
  {
    q: "Can it complete CAPTCHA challenges?",
    a: "CAPTCHA and browser compatibility restrictions can prevent automated registration. The agent does not bypass them. When one appears, the task pauses so you can complete it yourself, or you can use the manual fallback, when supported.",
  },
  {
    q: "Can it register me through Google, Facebook, X, or a passkey?",
    a: "Websites that exclusively require unsupported social-login or passkey flows cannot currently be registered through the ordinary automated registration workflow.",
  },
  {
    q: "Does it generate a unique password for each website?",
    a: "That is the intended behavior for supported registrations. Each password is generated randomly and the credentials are saved in the vault so you can retrieve them later.",
  },
  {
    q: "Can I read other messages sent to the temporary email address?",
    a: "Yes, when the associated inbox remains available through the supported email provider. Message availability depends on provider capabilities and retention rules.",
  },
  {
    q: "Do temporary accounts expire?",
    a: "Yes. Temporary account credentials are kept for a configured retention period (7 days by default) and are then scrubbed from the vault. The temporary inbox has its own expiry date, which the app shows, and message availability depends on the email provider.",
  },
  {
    q: "Do permanent accounts last forever?",
    a: "Permanent mode does not apply the temporary-account expiry rule to saved credentials. It does not guarantee that the external website, Gmail connection, or account will remain available forever.",
  },
  {
    q: "Is Temp Identity Agent a password manager?",
    a: "It includes a credential vault for accounts created through its own registration workflows, where you can reveal or delete each saved login. It does not currently import existing passwords or autofill them in your browser, so it is not a replacement for a dedicated password manager.",
  },
];
