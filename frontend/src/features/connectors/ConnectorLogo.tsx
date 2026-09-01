import type { ConnectorType } from "../../api/types";

/**
 * Simple, recognizable brand marks drawn as inline SVG (no external logo assets,
 * no advertising imagery). Each uses the service brand color as an accent.
 */
export function ConnectorLogo({ type, size = 40 }: { type: ConnectorType; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 48 48", "aria-hidden": true as const };
  switch (type) {
    case "whatsapp":
      return (
        <svg {...common}>
          <rect width="48" height="48" rx="12" fill="#25D366" />
          <path fill="#fff" d="M24 12a12 12 0 0 0-10.3 18.1L12 36l6.1-1.6A12 12 0 1 0 24 12Zm6.9 16.4c-.3.8-1.7 1.5-2.3 1.6-.6.1-1.3.1-2.1-.1-.5-.2-1.1-.4-1.9-.7-3.3-1.4-5.4-4.7-5.6-4.9-.2-.2-1.4-1.8-1.4-3.5s.9-2.5 1.2-2.8c.3-.3.7-.4.9-.4h.6c.2 0 .5 0 .7.5l1 2.4c.1.2.1.4 0 .6l-.4.6c-.2.2-.4.4-.2.8.2.4.9 1.5 2 2.4 1.3 1.2 2.4 1.5 2.8 1.7.3.1.5.1.7-.1l.9-1.1c.3-.3.5-.3.8-.2l2.3 1.1c.4.2.6.3.7.4.1.3.1.9-.2 1.7Z" />
        </svg>
      );
    case "telegram":
      return (
        <svg {...common}>
          <rect width="48" height="48" rx="12" fill="#2AABEE" />
          <path fill="#fff" d="M34.9 15.1 30.6 33c-.3 1.3-1.1 1.6-2.2 1L23 30.3l-2.8 2.7c-.3.3-.6.6-1.2.6l.4-5.8 10.5-9.5c.5-.4-.1-.6-.7-.2L16.4 24l-5.5-1.7c-1.2-.4-1.2-1.2.3-1.8l21.6-8.3c1-.4 1.9.2 1.5 1.9Z" />
        </svg>
      );
    case "google_drive":
      return (
        <svg {...common}>
          <rect width="48" height="48" rx="12" fill="#fff" stroke="#e6e8f0" />
          <path fill="#0F9D58" d="M18 12h12l10 17H28z" opacity="0.9" />
          <path fill="#4285F4" d="m8 29 6-10 8 14H14z" opacity="0.9" />
          <path fill="#FFCF63" d="m30 29 10 0-6 10H24z" opacity="0.9" />
        </svg>
      );
    case "google_photos":
      return (
        <svg {...common}>
          <rect width="48" height="48" rx="12" fill="#fff" stroke="#e6e8f0" />
          <path fill="#FBBC04" d="M23 10a6 6 0 0 1 6 6v7h-7v-7a6 6 0 0 1 1-6Z" transform="translate(1 1)" />
          <path fill="#EA4335" d="M38 23a6 6 0 0 1-6 6h-7v-7h7a6 6 0 0 1 6 1Z" transform="translate(-1 1)" />
          <path fill="#34A853" d="M25 38a6 6 0 0 1-6-6v-7h7v7a6 6 0 0 1-1 6Z" transform="translate(-1 -1)" />
          <path fill="#4285F4" d="M10 25a6 6 0 0 1 6-6h7v7h-7a6 6 0 0 1-6-1Z" transform="translate(1 -1)" />
        </svg>
      );
  }
}