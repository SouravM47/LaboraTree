// Laboratree mark — a lab flask with a sprout growing out (echoing the logo).

export default function BrandMark({ size = 30 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label="Laboratree"
    >
      {/* sprout leaves */}
      <path d="M16 7 C16 3.5 13 2.2 11.5 3.2 C12.5 5.5 14.5 7 16 7 Z" fill="#6DB33F" />
      <path d="M16 7 C16 3.5 19 2.2 20.5 3.2 C19.5 5.5 17.5 7 16 7 Z" fill="#A8D08D" />
      {/* liquid */}
      <path
        d="M10.6 18 H21.4 L24.2 23.2 A1.5 1.5 0 0 1 22.9 26.5 H9.1 A1.5 1.5 0 0 1 7.8 23.2 Z"
        fill="#6DB33F"
      />
      {/* flask outline */}
      <path
        d="M12 6 H20 M13.6 6.4 V12 L7.4 24 A1.6 1.6 0 0 0 8.8 26.5 H23.2 A1.6 1.6 0 0 0 24.6 24 L18.4 12 V6.4"
        stroke="#14342A"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
