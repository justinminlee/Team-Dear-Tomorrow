
import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

export type AvatarStyle =
  | "feminine"
  | "masculine"
  | "androgynous";

export type AvatarSettings = {
  style: AvatarStyle;
  skin: string;
  hair: string;
  outfit: string;
  hairstyle: "short" | "long";
};

type Props = {
  settings: AvatarSettings;
  yearsAhead: 5 | 10 | 15;
};

function Character({ settings, yearsAhead }: Props) {
  const head = useRef<THREE.Group>(null);
  const eyes = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;

    if (head.current) {
      head.current.position.y = Math.sin(t * 1.5) * 0.045;
      head.current.rotation.y = Math.sin(t * 0.7) * 0.12;
    }

    if (eyes.current) {
      const blink = Math.sin(t * 2.1) > 0.992;
      eyes.current.scale.y = blink ? 0.08 : 1;
    }

    if (mouth.current) {
      mouth.current.scale.y =
        0.7 + Math.abs(Math.sin(t * 3)) * 0.2;
    }
  });

  const maturity = yearsAhead / 15;

  const faceWidth =
  settings.style === "masculine"
    ? 0.96
    : settings.style === "feminine"
      ? 0.85
      : 0.9;

  const shoulderWidth = 
  settings.style === "masculine"
    ? 1.1
    : settings.style === "feminine"
      ? 0.85
      : 0.98;



  

  return (
    <group position={[0, -0.15, 0]}>
      {/* Body */}
      <mesh position={[0, -1.05, 0]}>
        <sphereGeometry args={[shoulderWidth, 32, 32]} />   
        <meshStandardMaterial color={settings.outfit} />
      </mesh>

      {/* Neck */}
      <mesh position={[0, -0.55, 0]}>
        <cylinderGeometry args={[0.22, 0.24, 0.5, 32]} />
        <meshStandardMaterial color={settings.skin} />
      </mesh>

      <group ref={head}>
        {/* Hair behind face */}
        {settings.hairstyle === "long" && (
          <mesh position={[0, -0.15, -0.25]}>
            <sphereGeometry args={[0.95, 40, 40]} />
            <meshStandardMaterial color={settings.hair} />
          </mesh>
        )}

        {/* Face */}
        <mesh scale={[faceWidth, 1 + maturity * 0.04, 0.74]}>
          <sphereGeometry args={[1, 48, 48]} />
          <meshStandardMaterial color={settings.skin} />
        </mesh>

        {/* Top hair */}
        <mesh position={[0, 0.59, -0.09]} scale={[0.92, 0.53, 0.77]}>
          <sphereGeometry args={[1, 40, 40]} />
          <meshStandardMaterial color={settings.hair} />
        </mesh>

        {/* Eyes */}
        <group ref={eyes}>
          {[-0.3, 0.3].map((x) => (
            <mesh key={x} position={[x, 0.12, 0.69]}>
              <sphereGeometry args={[0.11, 24, 24]} />
              <meshStandardMaterial color="#292332" />
            </mesh>
          ))}
        </group>

        {/* Nose */}
        <mesh position={[0, -0.1, 0.75]} scale={[0.1, 0.13, 0.1]}>
          <sphereGeometry args={[1, 20, 20]} />
          <meshStandardMaterial color={settings.skin} />
        </mesh>

        {/* Mouth */}
        <mesh ref={mouth} position={[0, -0.39, 0.68]}>
          <sphereGeometry args={[0.17, 0.055, 0.03, 24, 16]} />
          <meshStandardMaterial color="#A45F71" />
        </mesh>

        {/* Subtle age styling */}
        {yearsAhead === 15 && (
          <>
            {[-0.4, 0.4].map((x) => (
              <mesh
                key={x}
                position={[x, -0.27, 0.61]}
                rotation={[0, 0, x > 0 ? -0.2 : 0.2]}
              >
                <boxGeometry args={[0.12, 0.008, 0.008]} />
                <meshStandardMaterial color="#B88883" />
              </mesh>
            ))}
          </>
        )}
      </group>
    </group>
  );
}

export default function Avatar({ settings, yearsAhead }: Props) {
  return (
    <div style={{ width: "100%", height: 420 }}>
      <Canvas camera={{ position: [0, 0, 4.5], fov: 40 }}>
        <ambientLight intensity={1.7} />
        <directionalLight position={[3, 4, 5]} intensity={2} />
        <Character settings={settings} yearsAhead={yearsAhead} />
      </Canvas>
    </div>
  );
}

