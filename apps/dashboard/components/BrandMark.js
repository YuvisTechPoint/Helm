export default function BrandMark({ size = 30 }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="bm-bg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7c79ff" />
          <stop offset="1" stopColor="#4f46e5" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#bm-bg)" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="#fff" strokeOpacity="0.18" />
      <circle cx="12.5" cy="16" r="5.5" stroke="#fff" strokeWidth="2.2" />
      <circle cx="19.5" cy="16" r="5.5" stroke="#fff" strokeOpacity="0.7" strokeWidth="2.2" />
    </svg>
  );
}
