import { useCallback, useEffect, useRef, useState } from "react";

import { imageUrl } from "../api";
import type { Product } from "../api";
import "./MotionMedia.css";

type Props = {
  product: Product;
  /** Grid cards play on hover; the detail page waits for a deliberate click. */
  hoverToPlay?: boolean;
  className?: string;
};

/** True when the visitor has asked the OS for less animation. */
function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/**
 * Product media: a still by default, a short loop on demand.
 *
 * Three things the naive version gets wrong, all handled here:
 *
 * 1. **The video element is not rendered until it is wanted.** Putting a <video>
 *    in every card and hiding it with CSS still costs a metadata request per
 *    card; 102 of those on the storeroom page defeats the point. The element is
 *    mounted on first activation and kept thereafter.
 * 2. **`play()` returns a promise that can reject** — autoplay policy, or the
 *    pointer leaving before the file is ready. State is set from what actually
 *    happened, not from what was requested, so the button never lies.
 * 3. **The still stays mounted underneath** rather than being swapped out, so
 *    there is no flash of empty frame while the first video frame decodes.
 */
export default function MotionMedia({ product, hoverToPlay = false, className }: Props) {
  const motion = product.motion;
  const [active, setActive] = useState(false); // video element mounted
  const [ready, setReady] = useState(false); // has decodable data
  const [playing, setPlaying] = useState(false); // actually rolling
  const videoRef = useRef<HTMLVideoElement>(null);

  const start = useCallback(() => {
    if (!motion) return;
    setActive(true);
    const video = videoRef.current;
    if (!video) return; // first activation: the effect below starts it on mount
    video.play().then(
      () => setPlaying(true),
      () => setPlaying(false),
    );
  }, [motion]);

  const stop = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setPlaying(false);
    if (hoverToPlay) {
      // On a grid card, leaving the tile should restore the catalogue still
      // rather than freezing a half-zoomed frame in the middle of the grid.
      video.currentTime = 0;
      setReady(false);
    }
  }, [hoverToPlay]);

  // Kick off playback the first time the element appears.
  useEffect(() => {
    if (!active) return;
    const video = videoRef.current;
    if (!video) return;
    video.play().then(
      () => setPlaying(true),
      () => setPlaying(false),
    );
  }, [active]);

  if (!motion) {
    // The ~99 products with no loop render exactly as before.
    return (
      <img
        className={className}
        src={imageUrl(product)}
        alt={product.name}
        loading="lazy"
      />
    );
  }

  const hoverHandlers =
    hoverToPlay && !prefersReducedMotion()
      ? { onMouseEnter: start, onMouseLeave: stop }
      : {};

  return (
    <span className="motion" {...hoverHandlers}>
      <img
        className={className}
        src={imageUrl(product)}
        alt={product.name}
        loading="lazy"
      />

      {active && (
        <video
          ref={videoRef}
          /* Shown as soon as it can render a frame, not only while playing.
             Browsers refuse autoplay in several situations — a backgrounded tab
             pauses video-only media to save power — and gating visibility on
             `playing` meant the shopper pressed the button and saw nothing. A
             paused clip on its current frame is a fine thing to look at. */
          className={`motion__video${ready ? " motion__video--on" : ""}`}
          onLoadedData={() => setReady(true)}
          poster={imageUrl(product)}
          loop
          muted
          playsInline
          preload="metadata"
          aria-label={`${product.name} in motion: ${motion.caption}`}
        >
          {/* Order matters: the browser takes the first type it can play, so
              WebM leads and MP4 is the Safari fallback. */}
          <source src={motion.webm} type="video/webm" />
          <source src={motion.mp4} type="video/mp4" />
        </video>
      )}

      <button
        type="button"
        className="motion__toggle"
        aria-pressed={playing}
        onClick={(event) => {
          // The card is a link; a click on the toggle must not navigate.
          event.preventDefault();
          event.stopPropagation();
          playing ? stop() : start();
        }}
      >
        {playing ? "Pause" : "See in Motion"}
      </button>
    </span>
  );
}
