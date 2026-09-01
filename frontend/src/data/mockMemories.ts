import type { SearchResult } from "../api/types";

/**
 * SYNTHETIC demo dataset - clearly curated, NOT genuine user history (AGENTS.md).
 * Thumbnails are inline SVG data URIs so the demo renders without external assets.
 * This file is isolated from API code so it can be replaced by real Backend data.
 */

function svg(bg: string, fg: string, label: string, sub: string): string {
  const markup = `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="320">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${bg}"/><stop offset="1" stop-color="${fg}"/>
    </linearGradient></defs>
    <rect width="480" height="320" fill="url(#g)"/>
    <text x="32" y="150" font-family="Segoe UI, Arial" font-size="30" font-weight="700" fill="#ffffff">${label}</text>
    <text x="32" y="192" font-family="Segoe UI, Arial" font-size="18" fill="#e5e7ff">${sub}</text>
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(markup)}`;
}

export const MOCK_MEMORIES: SearchResult[] = [
  {
    id: "py-login-error",
    memorySource: "whatsapp",
    thumbnailUrl: svg("#111827", "#7C5CFC", "Python Login Error", "Traceback screenshot"),
    fullUrl: svg("#111827", "#7C5CFC", "Python Login Error", "KeyError: password"),
    title: "Python Login Error",
    description: "Traceback from the auth module when logging in.",
    category: "screenshot",
    ocrSnippet: 'Traceback (most recent call last): ... login() KeyError: "password"',
    matchScore: 0.96,
    sourceTag: "Screenshot",
    capturedAt: "2026-08-25T14:12:00.000Z",
    metadata: { project: "auth-service", language: "Python" },
    explanation: [
      { type: "ocr", label: 'OCR matched "Traceback" and "login"', icon: "text", strength: 0.94 },
      { type: "semantic", label: "Semantically related to Python errors", icon: "brain", strength: 0.9 },
      { type: "visual", label: "Visual match for a code/terminal screenshot", icon: "eye", strength: 0.72 },
      { type: "metadata", label: "Project metadata matched auth-service", icon: "database", strength: 0.6 },
    ],
  },
  {
    id: "code-auth",
    thumbnailUrl: svg("#0f172a", "#4F8CFF", "auth.py", "Login handler code"),
    fullUrl: svg("#0f172a", "#4F8CFF", "auth.py", "def login(request):"),
    title: "Auth Handler Code",
    description: "Login handler source referenced in the error.",
    category: "code",
    ocrSnippet: "def login(request): user = db.get(request['password'])",
    matchScore: 0.82,
    sourceTag: "Code",
    capturedAt: "2026-08-25T14:05:00.000Z",
    explanation: [
      { type: "ocr", label: 'OCR matched "def login"', icon: "text", strength: 0.8 },
      { type: "semantic", label: "Related to authentication logic", icon: "brain", strength: 0.77 },
    ],
  },
  {
    id: "py-traceback",
    thumbnailUrl: svg("#1f2937", "#7C5CFC", "Stack Trace", "Terminal output"),
    title: "Stack Trace",
    description: "Full terminal stack trace output.",
    category: "screenshot",
    ocrSnippet: "File 'auth.py', line 42, in login",
    matchScore: 0.74,
    sourceTag: "Screenshot",
  },
  {
    id: "cn-osi-slide",
    memorySource: "google_drive",
    thumbnailUrl: svg("#243B6B", "#4F8CFF", "OSI Model", "Lecture slide - 7 layers"),
    fullUrl: svg("#243B6B", "#4F8CFF", "OSI Model", "Physical -> Application"),
    title: "OSI Model Slide",
    description: "Lecture slide listing all seven OSI layers.",
    category: "slide",
    ocrSnippet: "OSI Model - 7 layers: Physical, Data Link, Network, Transport...",
    matchScore: 0.93,
    sourceTag: "Slide",
    capturedAt: "2026-08-10T09:30:00.000Z",
    metadata: { course: "Computer Networks" },
    explanation: [
      { type: "ocr", label: 'OCR matched "OSI Model"', icon: "text", strength: 0.95 },
      { type: "semantic", label: "Semantically related to Computer Networks", icon: "brain", strength: 0.88 },
    ],
  },
  {
    id: "cn-osi-hand",
    memorySource: "uploaded",
    thumbnailUrl: svg("#3b2f6b", "#7C5CFC", "OSI Notes", "Handwritten + diagram"),
    fullUrl: svg("#3b2f6b", "#7C5CFC", "OSI Notes", "Handwritten layer diagram"),
    title: "Handwritten OSI Notes",
    description: "Handwritten notes with a large layered diagram.",
    category: "note",
    ocrSnippet: "OSI model layers (handwritten) with large layer diagram",
    matchScore: 0.97,
    sourceTag: "Handwritten notes",
    capturedAt: "2026-08-12T18:20:00.000Z",
    metadata: { course: "Computer Networks" },
    explanation: [
      { type: "ocr", label: 'OCR matched "OSI"', icon: "text", strength: 0.86 },
      { type: "semantic", label: "Semantically related to Computer Networks", icon: "brain", strength: 0.9 },
      { type: "visual", label: "Visual match for handwritten notes", icon: "eye", strength: 0.92 },
      { type: "visual", label: "Large diagram detected", icon: "shapes", strength: 0.84 },
      { type: "clue", label: "Matched clue: handwritten", icon: "tag", strength: 0.8 },
    ],
  },
  {
    id: "cn-osi-typed",
    thumbnailUrl: svg("#243B6B", "#7C5CFC", "OSI Summary", "Typed revision notes"),
    title: "OSI Typed Summary",
    description: "Typed revision summary of OSI layers.",
    category: "note",
    ocrSnippet: "Layer 1 Physical ... Layer 7 Application",
    matchScore: 0.79,
    sourceTag: "Notes",
  },
  {
    id: "db-normal-hand",
    memorySource: "google_photos",
    thumbnailUrl: svg("#134e4a", "#4F8CFF", "Normalization", "Handwritten DBMS notes"),
    fullUrl: svg("#134e4a", "#4F8CFF", "Normalization", "1NF 2NF 3NF BCNF"),
    title: "DB Normalization Notes",
    description: "Handwritten notes on 1NF through BCNF.",
    category: "note",
    ocrSnippet: "Database normalization - 1NF, 2NF, 3NF, BCNF",
    matchScore: 0.88,
    sourceTag: "Handwritten notes",
    capturedAt: "2026-07-30T11:00:00.000Z",
    metadata: { course: "DBMS" },
    explanation: [
      { type: "ocr", label: 'OCR matched "normalization"', icon: "text", strength: 0.83 },
      { type: "semantic", label: "Semantically related to databases", icon: "brain", strength: 0.86 },
      { type: "visual", label: "Visual match for handwritten notes", icon: "eye", strength: 0.9 },
    ],
  },
  {
    id: "db-er-diagram",
    thumbnailUrl: svg("#134e4a", "#7C5CFC", "ER Diagram", "Entities and relations"),
    title: "ER Diagram",
    description: "Entity-relationship diagram for the notes.",
    category: "document",
    ocrSnippet: "Student -- enrolls --> Course",
    matchScore: 0.71,
    sourceTag: "Document",
  },
  {
    id: "receipt-cafe",
    memorySource: "telegram",
    thumbnailUrl: svg("#7c2d12", "#f59e0b", "Cafe Receipt", "Total INR 812"),
    fullUrl: svg("#7c2d12", "#f59e0b", "Cafe Receipt", "Subtotal 720 + tax"),
    title: "Cafe Receipt",
    description: "Receipt from a cafe visit.",
    category: "receipt",
    ocrSnippet: "Total: INR 812.00  -  Thank you!",
    matchScore: 0.9,
    sourceTag: "Receipt",
    capturedAt: "2026-08-01T13:40:00.000Z",
    metadata: { total: "INR 812" },
    explanation: [
      { type: "ocr", label: 'OCR matched "Total" and amount', icon: "text", strength: 0.91 },
      { type: "metadata", label: "Amount is close to INR 800", icon: "database", strength: 0.7 },
    ],
  },
  {
    id: "arch-diagram",
    thumbnailUrl: svg("#1e293b", "#7C5CFC", "Architecture", "System diagram"),
    fullUrl: svg("#1e293b", "#7C5CFC", "Architecture", "Frontend -> API -> AI"),
    title: "Project Architecture Diagram",
    description: "High-level system architecture screenshot.",
    category: "document",
    ocrSnippet: "Frontend -> FastAPI -> Agent -> Retrieval",
    matchScore: 0.85,
    sourceTag: "Diagram",
    explanation: [
      { type: "visual", label: "Large diagram detected", icon: "shapes", strength: 0.88 },
      { type: "semantic", label: "Related to system architecture", icon: "brain", strength: 0.8 },
    ],
  },
  {
    id: "meme-confused",
    thumbnailUrl: svg("#4c1d95", "#7C5CFC", "Reaction Meme", "Little text"),
    title: "Confused Reaction Meme",
    description: "A meme retrieved mainly by visual similarity.",
    category: "other",
    matchScore: 0.87,
    sourceTag: "Meme",
    explanation: [
      { type: "visual", label: "Visual similarity to a confused-person reaction image", icon: "eye", strength: 0.87 },
    ],
  },
];
