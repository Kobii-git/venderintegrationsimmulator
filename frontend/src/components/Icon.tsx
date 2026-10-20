import type { CSSProperties } from "react";

const paths = {
  layers: "m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5",
  lab: "M9 3h6M10 3v7L4 20h16l-6-10V3M8 15h8",
  code: "m8 8-4 4 4 4m8-8 4 4-4 4m-3-11-2 14",
  upload: "M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  book: "M12 5v16M3 3l9 2 9-2v16l-9 2-9-2V3Z",
  plus: "M12 5v14M5 12h14",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "m6 6 12 12M6 18 18 6",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  check: "m5 12 4 4L19 6",
  search: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z",
} as const;

export function Icon({ name, style }: { name: keyof typeof paths; style?: CSSProperties }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      className="icon" style={style}>
      <path d={paths[name]} />
    </svg>
  );
}
