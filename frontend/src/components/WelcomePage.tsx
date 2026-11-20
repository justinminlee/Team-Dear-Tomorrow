import { useEffect, useRef, useState } from "react";
import "./WelcomePage.css";

export type WelcomePageProps = {
  onEnter?: () => void;
  onStartQuestionnaire?: () => void;
  imageSrc?: string;
};

/** Ported from the approved Me² Ripple HTML preview (no Motion dependency). */
export default function WelcomePage({
  onEnter,
  onStartQuestionnaire,
  imageSrc = "/me2_phonebooth.png",
}: WelcomePageProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const bloomRef = useRef<HTMLDivElement>(null);
  const ring1Ref = useRef<HTMLDivElement>(null);
  const ring2Ref = useRef<HTMLDivElement>(null);
  const whiteRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef(false);
  const animationsRef = useRef<Animation[]>([]);
  const [nextVisible, setNextVisible] = useState(false);

  useEffect(() => () => {
    animationsRef.current.forEach((animation) => animation.cancel());
    animationsRef.current = [];
  }, []);

  const reset = () => {
    animationsRef.current.forEach((a) => a.cancel());
    animationsRef.current = [];
    activeRef.current = false;
    setNextVisible(false);
  };

  const start = async () => {
    if (activeRef.current) return;
    const root = rootRef.current;
    const img = imgRef.current;
    const bloom = bloomRef.current;
    const whiteout = whiteRef.current;
    const rings = [ring1Ref.current, ring2Ref.current];
    if (!root || !img || !bloom || !whiteout || rings.some((r) => !r)) return;
    activeRef.current = true;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      if (onEnter) onEnter();
      else setNextVisible(true);
      return;
    }

    // Match the same LCD point (.575, .514) as the approved HTML preview.
    const rect = img.getBoundingClientRect();
    const container = root.getBoundingClientRect();
    const x = rect.left - container.left + rect.width * 0.575;
    const y = rect.top - container.top + rect.height * 0.514;
    bloom.style.left = `${x}px`;
    bloom.style.top = `${y}px`;
    rings.forEach((ring) => {
      if (!ring) return;
      ring.style.left = `${x}px`;
      ring.style.top = `${y}px`;
    });

    const finalRadius = Math.hypot(
      Math.max(x, container.width - x),
      Math.max(y, container.height - y)
    ) * 1.5;

    const pulse = bloom.animate([
      { opacity: 0, transform: "translate(-50%,-50%) scale(15)", offset: 0 },
      { opacity: 0.9, transform: "translate(-50%,-50%) scale(90)", offset: 0.3 },
      { opacity: 1, transform: `translate(-50%,-50%) scale(${finalRadius * 1.4})`, offset: 1 },
    ], { duration: 1600, fill: "forwards", easing: "cubic-bezier(.16,.75,.12,1)" });

    const waves = rings.map((ring, i) => ring!.animate([
      { opacity: 0, transform: "translate(-50%,-50%) scale(8)", offset: 0 },
      { opacity: 0.88, transform: "translate(-50%,-50%) scale(45)", offset: 0.2 },
      { opacity: 0.5, transform: `translate(-50%,-50%) scale(${finalRadius * 0.7})`, offset: 0.75 },
      { opacity: 0, transform: `translate(-50%,-50%) scale(${finalRadius})`, offset: 1 },
    ], { duration: 1250, delay: i * 145, fill: "forwards", easing: "cubic-bezier(.18,.7,.18,1)" }));

    const flash = whiteout.animate([
      { opacity: 0, offset: 0 },
      { opacity: 0, offset: 0.7 },
      { opacity: 1, offset: 1 },
    ], { duration: 1600, fill: "forwards", easing: "ease-in" });

    const zoom = img.animate([
      { transform: "scale(1)", filter: "brightness(1)" },
      { transform: "scale(1.025)", filter: "brightness(1.05)" },
    ], { duration: 1100, fill: "forwards", easing: "ease-out" });

    animationsRef.current = [pulse, ...waves, flash, zoom];
    try {
      await Promise.all([pulse.finished, flash.finished]);
      if (!root.isConnected) return;
      // The next view is revealed *under* the whiteout.
      if (onEnter) {
        onEnter();
      } else {
        setNextVisible(true);
        const fade = whiteout.animate([{ opacity: 1 }, { opacity: 0 }],
          { duration: 380, fill: "forwards" });
        animationsRef.current.push(fade);
        await fade.finished;
        if (root.isConnected) {
          animationsRef.current.forEach((a) => a.cancel());
          animationsRef.current = [];
        }
      }
    } catch {
      // Component may unmount while navigating; cancellation is expected.
    }
  };

  return (
    <div className="me2-welcome" ref={rootRef}>
      <main className="me2-welcome__main">
        <h1 className="me2-headline"><em>Click</em> the <em>telephone</em> to<br />talk to your <em>future self</em></h1>
        <p className="me2-hint">YOUR FUTURE SELF IS CALLING</p>
        <button className="me2-booth" type="button" disabled={activeRef.current || nextVisible}
          aria-label="Enter phone booth and begin" onClick={start}>
          <img src={imageSrc} alt="An amber-lit Me² public telephone booth" ref={imgRef} />
        </button>
      </main>
      <div className="me2-light-bloom" ref={bloomRef} aria-hidden="true" />
      <div className="me2-ripple-ring" ref={ring1Ref} aria-hidden="true" />
      <div className="me2-ripple-ring" ref={ring2Ref} aria-hidden="true" />
      <div className="me2-whiteout" ref={whiteRef} aria-hidden="true" />
      {!onEnter && (
        <div className={`me2-next${nextVisible ? " visible" : ""}`} aria-hidden={!nextVisible}>
          <section>
            <p>Me² · A CONVERSATION ACROSS TIME</p>
            <h2>Your future begins here.</h2>
            <p>This is the next screen placeholder. Connect this view to your real questionnaire route.</p>
            <button type="button" onClick={onStartQuestionnaire}> Start questionnaire → </button>
            <button type="button" className="back" onClick={reset}>← Back to welcome</button>
          </section>
        </div>
      )}
    </div>
  );
}
