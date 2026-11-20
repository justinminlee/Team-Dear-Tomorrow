
import { useState } from "react";
import Tomorrow from "./Tomorrow";

type LandingPageProps = {
  onGetStarted: () => void;
};

export default function LandingPage({
  onGetStarted,
}: LandingPageProps) {
  const [tomorrowActive, setTomorrowActive] = useState(false);
  const [tomorrowSpeaking, setTomorrowSpeaking] = useState(false);

  function summonTomorrow() {
    setTomorrowActive(true);
    setTomorrowSpeaking(true);

    window.setTimeout(() => {
      setTomorrowSpeaking(false);
    }, 1800);
  }

  return (
    <main className="landing-page">
      <div className="landing-content">

        <h1 className="landing-logo">
          Me<sup>2</sup> AI
        </h1>

        <p className="landing-tagline">
          Meet your future self.
        </p>

        <div className="landing-sphere">
          <Tomorrow
            active={tomorrowActive}
            speaking={tomorrowSpeaking}
          />
        </div>

        <button
          className="landing-button"
          onClick={
            tomorrowActive
              ? onGetStarted
              : summonTomorrow
          }
        >
          {tomorrowActive
            ? "Get Started →"
            : "Start Tomorrow →"}
        </button>

        <p className="landing-footer">
          Discover who you could become.
        </p>

      </div>
    </main>
  );
}
