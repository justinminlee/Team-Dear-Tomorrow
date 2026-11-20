
import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

type LandingPageProps = {
  onGetStarted: () => void;
};

function FloatingSphere() {
  const sphereRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (!sphereRef.current) return;

    const time = clock.getElapsedTime();

    sphereRef.current.position.y =
      Math.sin(time * 1.1) * 0.12;

    sphereRef.current.rotation.y = time * 0.15;
    sphereRef.current.rotation.z =
      Math.sin(time * 0.4) * 0.08;
  });

  return (
    <mesh ref={sphereRef}>
      <sphereGeometry args={[1.3, 64, 64]} />
      <meshPhysicalMaterial
        color="#B99BEA"
        roughness={0.45}
        metalness={0.05}
        clearcoat={0.35}
        clearcoatRoughness={0.25}
      />
    </mesh>
  );
}

export default function LandingPage({
  onGetStarted,
}: LandingPageProps) {
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
          <Canvas
            camera={{ position: [0, 0, 5], fov: 45 }}
            dpr={[1, 2]}
          >
            <ambientLight intensity={1.8} />

            <directionalLight
              position={[3, 5, 5]}
              intensity={2.5}
              color="#ffffff"
            />

            <pointLight
              position={[-3, -2, 3]}
              intensity={2}
              color="#9572DD"
            />

            <FloatingSphere />
          </Canvas>
        </div>

        <button
          className="landing-button"
          onClick={onGetStarted}
        >
          Get Started <span aria-hidden="true">→</span>
        </button>

        <p className="landing-footer">
          Discover who you could become.
        </p>
      </div>
    </main>
  );
}
