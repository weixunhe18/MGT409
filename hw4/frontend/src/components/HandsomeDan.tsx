/**
 * Handsome Dan — Yale's Olde English Bulldogge, drawn rather than downloaded so
 * the shop ships no image it does not own.
 *
 * Likeness checked against the real mascot. What makes it read as a bulldog
 * rather than a bear: a head much wider than tall, small folded rose ears at the
 * corners, the thick nose-roll fold, heavy jowls that hang below the jaw, and an
 * underbite with lower canines showing. White coat with a brindle patch over one
 * eye; stocky neck and chest. Every white mass is outlined, or the jowls and
 * teeth disappear into the face.
 */
const OUTLINE = "#cdbfa9";
const INK = "#2a1e15";
const COAT = "#fffdf8";
const BRINDLE = "#9c6b45";

export default function HandsomeDan({ size = 44 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Handsome Dan, the Yale bulldog"
    >
      <defs>
        <clipPath id="dan-clip">
          <circle cx="50" cy="50" r="50" />
        </clipPath>
      </defs>

      <g clipPath="url(#dan-clip)" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="50" cy="50" r="50" fill="var(--dan-bg, #dce8f4)" />

        {/* Stocky chest and shoulders */}
        <ellipse cx="50" cy="104" rx="50" ry="28" fill={COAT} stroke={OUTLINE} strokeWidth="1.4" />

        {/* Collar */}
        <path d="M8 90 Q50 101 92 90 L92 104 L8 104 Z" fill="var(--accent, #00356b)" />
        <text x="50" y="99.5" textAnchor="middle" fontFamily="Georgia, serif" fontSize="8" fontWeight="bold" fill="#fff">
          Y
        </text>

        {/* Head — wide and squat */}
        <path
          d="M50 19C73 19 88 29 89 46C90 62 81 74 66 79H34C19 74 10 62 11 46C12 29 27 19 50 19Z"
          fill={COAT}
          stroke={OUTLINE}
          strokeWidth="1.4"
        />

        {/* Rose ears — small, folded back, at the corners of the skull */}
        <path d="M13 37C7 32 7 23 15 21C22 19 28 25 28 32C22 32 17 34 13 37Z" fill={BRINDLE} />
        <path d="M87 37C93 32 93 23 85 21C78 19 72 25 72 32C78 32 83 34 87 37Z" fill="#c9a786" />

        {/* Brindle patch over the left eye */}
        <path d="M22 38C26 30 37 28 44 33C48 37 47 46 41 50C35 53 26 51 23 46C21 43 21 41 22 38Z" fill={BRINDLE} />

        {/* Forehead wrinkles */}
        <path d="M38 29Q50 24 62 29" stroke={OUTLINE} strokeWidth="2" fill="none" />
        <path d="M41 34Q50 30 59 34" stroke={OUTLINE} strokeWidth="1.8" fill="none" />

        {/* Eyes — wide-set, low, a little droopy */}
        <circle cx="34" cy="43" r="4.4" fill={INK} />
        <circle cx="66" cy="43" r="4.4" fill={INK} />
        <circle cx="35.4" cy="41.6" r="1.4" fill="#fff" />
        <circle cx="67.4" cy="41.6" r="1.4" fill="#fff" />
        <path d="M29.5 47.5Q34 50 38.5 47.5" stroke="#d98f86" strokeWidth="1.3" fill="none" />
        <path d="M61.5 47.5Q66 50 70.5 47.5" stroke="#d98f86" strokeWidth="1.3" fill="none" />

        {/* Heavy jowls hanging below the jaw line */}
        <path
          d="M50 60C40 57 25 61 23 71C21 80 32 86 43 83C48 82 50 78 50 73Z"
          fill={COAT}
          stroke={OUTLINE}
          strokeWidth="1.5"
        />
        <path
          d="M50 60C60 57 75 61 77 71C79 80 68 86 57 83C52 82 50 78 50 73Z"
          fill={COAT}
          stroke={OUTLINE}
          strokeWidth="1.5"
        />

        {/* Nose roll — the thick fold that sits over a bulldog's nose */}
        <path d="M33 53Q50 43 67 53" stroke={OUTLINE} strokeWidth="3.2" fill="none" />

        {/* Broad, flat nose */}
        <ellipse cx="50" cy="56" rx="9.5" ry="5.6" fill={INK} />
        <ellipse cx="46" cy="56.6" rx="1.6" ry="2.1" fill="#5a4636" />
        <ellipse cx="54" cy="56.6" rx="1.6" ry="2.1" fill="#5a4636" />
        <ellipse cx="47.5" cy="53.8" rx="2.6" ry="1" fill="#6b5646" />

        {/* Philtrum */}
        <path d="M50 61.5V72" stroke={INK} strokeWidth="1.6" />

        {/* Underbite: jutting lower jaw between the jowls */}
        <path d="M40 81C44 89 56 89 60 81C56 84 44 84 40 81Z" fill="#7a3f3a" />
        <path d="M38 81C43 92 57 92 62 81" stroke={OUTLINE} strokeWidth="1.5" fill={COAT} />

        {/* Lower canines poking up over the lip */}
        <path d="M42.5 82L44 75.5L46 82Z" fill="#fffef9" stroke="#a89a85" strokeWidth="0.9" />
        <path d="M54 82L56 75.5L57.5 82Z" fill="#fffef9" stroke="#a89a85" strokeWidth="0.9" />
      </g>
    </svg>
  );
}
