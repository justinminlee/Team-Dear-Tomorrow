import LandingPage from "./components/LandingPage";
import { useEffect, useState } from "react";
import Avatar, {
  type AvatarSettings,
} from "./components/Avatar";
import "./App.css";

type FutureYear = 5 | 10 | 15;

function App() {
  const [showCreator, setShowCreator] = useState(false);
  const [yearsAhead, setYearsAhead] = useState<FutureYear>(5);
  const [selfie, setSelfie] = useState<string | null>(null);

  const [settings, setSettings] = useState<AvatarSettings>({
    style: "feminine",
    skin: "#E8B99F",
    hair: "#30233D",
    outfit: "#A994DE",
    hairstyle: "long",
  });   

  useEffect(() => {
    return () => {
      if (selfie) URL.revokeObjectURL(selfie);
    };
  }, [selfie]);

  function updateSetting<K extends keyof AvatarSettings>(
    key: K,
    value: AvatarSettings[K]
  ) {
    setSettings((previous) => ({
      ...previous,
      [key]: value,
    }));
  }

  function uploadSelfie(file?: File) {
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Please select an image.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      alert("Please choose an image smaller than 10 MB.");
      return;
    }

    setSelfie(URL.createObjectURL(file));
  }
  
  if (!showCreator) {
    return (
      <LandingPage
        onGetStarted={() => setShowCreator(true)}
      />
    );
  }

  return (
    <div className="app">
      <header className="navbar">
        <div className="logo">
          me²<span>AI</span>
        </div>
        <span className="nav-label">FUTURE SELF CREATOR</span>
      </header>

      <main className="creator-layout">
        <section className="creator-panel">
          <p className="eyebrow">STEP 01 — PERSONALISE</p>
          <h1>Create your future self.</h1>
          
          <p className="description">
            Design a version of yourself and explore
            who you might become.
          </p>
          

          {/* NEW: Avatar style selector */}
          <h3>Choose your avatar style</h3>

          <div className="option-buttons">
            {(["feminine", "masculine", "androgynous"] as const).map(
              (style) => (
                <button
                  key={style}
                  className={
                    settings.style === style
                      ? "selected-option"
                      : ""
                  }
                  onClick={() => {
                    setSettings((previous) => ({
                      ...previous,
                      style,
                      hairstyle:
                        style === "masculine" ? "short" : "long",
                    }));
                  }}
                >
                  {style.charAt(0).toUpperCase() + style.slice(1)}
                </button>
              )
            )}
          </div>


          <h3>Upload your selfie</h3>
          <label className="upload-box">
            {selfie ? (
              <img src={selfie} alt="Your uploaded selfie" />
            ) : (
              <span>＋ Choose a photo</span>
            )}

            <input
              type="file"
              accept="image/*"
              onChange={(e) =>
                uploadSelfie(e.target.files?.[0])
              }
            />
          </label>

          <p className="helper-text">
            Your photo is previewed locally in this
            prototype. It does not yet generate a 3D face.
          </p>

          <h3>Skin tone</h3>
          <div className="swatches">
            {[
              "#F6D9C5",
              "#E8B99F",
              "#C58C6C",
              "#956345",
              "#5E3D30",
            ].map((color) => (
              <button
                key={color}
                className={
                  settings.skin === color
                    ? "swatch selected"
                    : "swatch"
                }
                style={{ background: color }}
                onClick={() => updateSetting("skin", color)}
                aria-label={`Select skin tone ${color}`}
              />
            ))}
          </div>

          <h3>Hair colour</h3>
          <div className="swatches">
            {[
              "#30233D",
              "#75503C",
              "#C99A60",
              "#A65E68",
            ].map((color) => (
              <button
                key={color}
                className={
                  settings.hair === color
                    ? "swatch selected"
                    : "swatch"
                }
                style={{ background: color }}
                onClick={() => updateSetting("hair", color)}
                aria-label={`Select hair colour ${color}`}
              />
            ))}
          </div>

          <h3>Hairstyle</h3>
          <div className="option-buttons">
            {(["short", "long"] as const).map((style) => (
              <button
                key={style}
                className={
                  settings.hairstyle === style
                    ? "selected-option"
                    : ""
                }
                onClick={() =>
                  updateSetting("hairstyle", style)
                }
              >
                {style}
              </button>
            ))}
          </div>

          <h3>Outfit colour</h3>
          <div className="swatches">
            {[
              "#A994DE",
              "#D989A8",
              "#7399A7",
              "#333B57",
            ].map((color) => (
              <button
                key={color}
                className={
                  settings.outfit === color
                    ? "swatch selected"
                    : "swatch"
                }
                style={{ background: color }}
                onClick={() => updateSetting("outfit", color)}
                aria-label={`Select outfit colour ${color}`}
              />
            ))}
          </div>
        </section>

        <section className="preview-panel">
          <p className="eyebrow">STEP 02 — EXPLORE</p>
          <h2>Meet your future self</h2>

          <div className="future-options">
            {([5, 10, 15] as FutureYear[]).map((year) => (
              <button
                key={year}
                className={
                  yearsAhead === year ? "active" : ""
                }
                onClick={() => setYearsAhead(year)}
              >
                +{year} years
              </button>
            ))}
          </div>

          <div className="avatar-stage">
            <Avatar
              settings={settings}
              yearsAhead={yearsAhead}
            />
          </div>

          <div className="future-caption">
            YOU, {yearsAhead} YEARS FROM NOW
          </div>

          <p className="helper-text">
            A creative simulation of a possible future,
            not a prediction.
          </p>
        </section>
      </main>
    </div>
  );
}

export default App;
