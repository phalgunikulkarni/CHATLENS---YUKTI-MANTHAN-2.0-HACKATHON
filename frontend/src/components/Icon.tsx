import type { CSSProperties } from "react";

export type IconName =
  | "search" | "sparkles" | "upload" | "library" | "history" | "brain"
  | "eye" | "text" | "shapes" | "database" | "tag" | "close" | "check"
  | "grid" | "list" | "arrow" | "calendar" | "summary" | "map" | "menu"
  | "chevron" | "wifi-off" | "image" | "layers";

interface IconProps {
  name: IconName;
  size?: number;
  style?: CSSProperties;
  className?: string;
}

/** Minimal inline-SVG icon set (no icon dependency, keeps bundle small). */
const PATHS: Record<IconName, string> = {
  search: "M11 4a7 7 0 1 0 4.2 12.6l4.1 4.1 1.4-1.4-4.1-4.1A7 7 0 0 0 11 4Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z",
  sparkles: "M12 2l1.8 4.2L18 8l-4.2 1.8L12 14l-1.8-4.2L6 8l4.2-1.8L12 2Zm6 10l1 2.4L21.5 15l-2.5 1 -1 2.4-1-2.4L14.5 15l2.5-.6L18 12Z",
  upload: "M12 3l4 4h-3v7h-2V7H8l4-4Zm-7 14h14v2H5v-2Z",
  library: "M4 5h4v14H4V5Zm6 0h4v14h-4V5Zm7 1l3 12-3 .7-3-12L17 6Z",
  history: "M13 3a9 9 0 1 0 8.5 12H19a7 7 0 1 1-6-10 7 7 0 0 1 6.7 5H16l4 4 4-4h-2.1A9 9 0 0 0 13 3Zm-1 4v6l5 3 .9-1.6L14 12V7h-2Z",
  brain: "M8 3a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8V15a3 3 0 0 0 4 2.8V21h2V5a2 2 0 0 0-2-2Zm8 0a2 2 0 0 0-2 2v16h2v-3.2A3 3 0 0 0 20 15v-3.2A3 3 0 0 0 19 6a3 3 0 0 0-3-3Z",
  eye: "M12 5C6 5 2 12 2 12s4 7 10 7 10-7 10-7-4-7-10-7Zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0-2a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  text: "M4 5h16v2H4V5Zm0 4h16v2H4V9Zm0 4h10v2H4v-2Zm0 4h16v2H4v-2Z",
  shapes: "M12 2l4 7H8l4-7ZM5 13a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm8 1h8v7h-8v-7Z",
  database: "M12 3c-4.4 0-8 1.3-8 3v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6c0-1.7-3.6-3-8-3Zm6 15c0 .5-2.4 1.5-6 1.5S6 18.5 6 18v-2.3c1.5.8 3.7 1.3 6 1.3s4.5-.5 6-1.3V18Zm0-5c0 .5-2.4 1.5-6 1.5S6 13.5 6 13v-2.3c1.5.8 3.7 1.3 6 1.3s4.5-.5 6-1.3V13Zm-6-3.5C8.4 9.5 6 8.5 6 8s2.4-1.5 6-1.5S18 7.5 18 8s-2.4 1.5-6 1.5Z",
  tag: "M2 12l9-9 9 9-9 9-9-9Zm6-3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z",
  close: "M6 5l6 6 6-6 1.4 1.4-6 6 6 6L18 19l-6-6-6 6L4.6 17.6l6-6-6-6L6 5Z",
  check: "M9 16.2l-3.5-3.5L4 14.2 9 19l11-11-1.4-1.4L9 16.2Z",
  grid: "M3 3h8v8H3V3Zm10 0h8v8h-8V3ZM3 13h8v8H3v-8Zm10 0h8v8h-8v-8Z",
  list: "M4 5h16v2H4V5Zm0 6h16v2H4v-2Zm0 6h16v2H4v-2Z",
  arrow: "M4 11h12.2l-5.6-5.6L12 4l8 8-8 8-1.4-1.4 5.6-5.6H4v-2Z",
  calendar: "M7 2v2H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7Zm12 7v10H5V9h14Z",
  summary: "M4 4h16v2H4V4Zm0 5h16v2H4V9Zm0 5h11v2H4v-2Zm0 5h11v2H4v-2Z",
  map: "M15 4l6-2v16l-6 2-6-2-6 2V4l6-2 6 2Zm-1 2.2L10 4.8v13l4 1.4v-13Z",
  menu: "M3 6h18v2H3V6Zm0 5h18v2H3v-2Zm0 5h18v2H3v-2Z",
  chevron: "M9 6l6 6-6 6-1.4-1.4L12.2 12 7.6 7.4 9 6Z",
  "wifi-off": "M2 4.3L3.3 3 21 20.7 19.7 22l-3-3H12v-2l1.5-.1L2 4.3ZM12 3c3 0 5.8 1.1 8 3l-2 2a8.6 8.6 0 0 0-4.3-1.8L12 3Z",
  image: "M4 4h16v16H4V4Zm2 2v9l4-4 3 3 3-3 2 2V6H6Zm3 2a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z",
  layers: "M12 2l10 6-10 6L2 8l10-6Zm0 9.6L4.7 7 2 8.6l10 6 10-6L19.3 7 12 11.6ZM2 15l10 6 10-6-2-1.2-8 4.8-8-4.8L2 15Z",
};

export function Icon({ name, size = 20, style, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
      style={style}
      className={className}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
